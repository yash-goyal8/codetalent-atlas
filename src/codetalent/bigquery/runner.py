"""Guarded BigQuery execution: dry-run first, budget ledger, byte caps.

Non-negotiable cost-safety rules enforced here (spec sections 13 and 26):

1. Every execution path dry-runs first (free), logs the estimate, and checks
   the cumulative phase ledger BEFORE running; execution is refused when the
   cumulative executed bytes plus the new estimate would exceed
   ``BIGQUERY_MAX_BYTES_PHASE3``.
2. Every executed job sets ``maximum_bytes_billed`` (estimate * 1.25, rounded
   up, with a small floor) so BigQuery itself kills any underestimated query.
3. Every query — dry run and real — is appended to ``reports/query_usage.csv``
   with its existing header preserved exactly.
4. Month grid materialization is idempotent: a destination that already exists
   with rows is skipped (resume semantics, no double spend).

The project is a BigQuery Sandbox with no billing account attached; nothing
here can create a charge, these guards preserve the free monthly quota.
"""

from __future__ import annotations

import csv
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.api_core.exceptions import NotFound
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

from codetalent.bigquery.dry_run import QuerySpec
from codetalent.runlog import RunLogger
from codetalent.settings import Settings

USAGE_REPORT_PATH = Path("reports/query_usage.csv")
USAGE_HEADER: tuple[str, ...] = (
    "timestamp",
    "phase",
    "query_name",
    "estimated_bytes",
    "actual_bytes",
    "runtime_seconds",
    "status",
)
PHASE3 = "phase3"

# maximum_bytes_billed = ceil(estimate * SAFETY_FACTOR), never below the floor
# (so 0-byte estimates such as DDL still get a real, tiny cap).
SAFETY_FACTOR = 1.25
MIN_MAX_BYTES_BILLED = 10 * 1024 * 1024

# Ledger statuses. Only statuses in _CONSUMING_STATUSES count against the
# budget: dry runs are free, skipped queries never ran, refused queries were
# blocked before running.
STATUS_DRY_RUN = "dry_run"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"
STATUS_REFUSED = "refused"
_CONSUMING_STATUSES = frozenset({STATUS_SUCCESS, STATUS_ERROR})

# Sandbox tables expire automatically; keep results just under the sandbox's
# 60-day ceiling so every later milestone can re-read the grids.
DEFAULT_TABLE_EXPIRATION_MS = 55 * 24 * 60 * 60 * 1000

CREDENTIALS_INSTRUCTIONS = (
    "Google Cloud credentials are not available. Set up free Application "
    "Default Credentials for the BigQuery Sandbox project (no billing):\n"
    "  1. gcloud auth application-default login\n"
    "  2. gcloud auth application-default set-quota-project <your-project-id>\n"
    "  3. Ensure GOOGLE_CLOUD_PROJECT is set in your local .env"
)


class BudgetExceededError(RuntimeError):
    """Executing the query would push the phase over its byte budget."""


class LedgerFormatError(RuntimeError):
    """reports/query_usage.csv does not match the required header."""


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class QueryUsageLedger:
    """Append-only accounting of every dry-run and executed query."""

    def __init__(self, path: Path = USAGE_REPORT_PATH) -> None:
        self.path = path

    def _check_or_create_header(self) -> None:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(USAGE_HEADER)
            return
        with self.path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), None)
        if header != list(USAGE_HEADER):
            raise LedgerFormatError(
                f"{self.path} header must be {','.join(USAGE_HEADER)!r}, got {header!r}"
            )

    def append(
        self,
        *,
        phase: str,
        query_name: str,
        estimated_bytes: int,
        actual_bytes: int,
        runtime_seconds: float,
        status: str,
    ) -> None:
        """Append one row, creating the file (or validating its header) first."""
        self._check_or_create_header()
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                [
                    _utc_timestamp(),
                    phase,
                    query_name,
                    estimated_bytes,
                    actual_bytes,
                    round(runtime_seconds, 3),
                    status,
                ]
            )

    def consumed_bytes(self, phase: str) -> int:
        """Bytes already spent by executed queries of this phase.

        Each executed row (success or error) contributes
        ``max(estimated_bytes, actual_bytes)`` — conservative when a job failed
        mid-flight and only the estimate is reliable. Dry-run, skipped, and
        refused rows are free and contribute nothing.
        """
        if not self.path.exists():
            return 0
        consumed = 0
        with self.path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != list(USAGE_HEADER):
                raise LedgerFormatError(
                    f"{self.path} header must be {','.join(USAGE_HEADER)!r}, "
                    f"got {reader.fieldnames!r}"
                )
            for row in reader:
                if row.get("phase") != phase or row.get("status") not in _CONSUMING_STATUSES:
                    continue
                estimated = _to_int(row.get("estimated_bytes"))
                actual = _to_int(row.get("actual_bytes"))
                consumed += max(estimated, actual)
        return consumed


def _to_int(value: str | None) -> int:
    try:
        return int(value) if value else 0
    except ValueError:
        return 0


def build_client(settings: Settings) -> bigquery.Client:
    """Construct the REST BigQuery client from Settings (ADC credentials)."""
    if not settings.google_cloud_project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is not set. Add it to your local .env (see .env.example)."
        )
    try:
        return bigquery.Client(project=settings.google_cloud_project)
    except DefaultCredentialsError as exc:
        raise RuntimeError(CREDENTIALS_INSTRUCTIONS) from exc


def assert_within_budget(estimated_bytes: int, consumed_bytes: int, max_bytes: int) -> None:
    """Refuse before execution when the estimate would blow the phase budget."""
    if consumed_bytes + estimated_bytes > max_bytes:
        raise BudgetExceededError(
            f"refusing to execute: {consumed_bytes} bytes already consumed plus "
            f"{estimated_bytes} estimated would exceed the phase budget of {max_bytes} bytes "
            "(BIGQUERY_MAX_BYTES_PHASE3)"
        )


def maximum_bytes_billed_for(estimated_bytes: int) -> int:
    """Per-job byte cap: estimate * 1.25 rounded up, floored for 0-byte jobs."""
    return max(math.ceil(estimated_bytes * SAFETY_FACTOR), MIN_MAX_BYTES_BILLED)


@dataclass(frozen=True)
class ExecutionOutcome:
    """Result of one guarded plan step."""

    query_name: str
    status: str
    estimated_bytes: int
    actual_bytes: int
    rows: list[dict[str, Any]] | None = None


class BigQueryRunner:
    """Render → dry-run → guard → execute lifecycle for the discovery plan."""

    def __init__(
        self,
        client: bigquery.Client,
        settings: Settings,
        *,
        ledger: QueryUsageLedger | None = None,
        logger: RunLogger | None = None,
        phase: str = PHASE3,
    ) -> None:
        self.client = client
        self.settings = settings
        self.ledger = ledger if ledger is not None else QueryUsageLedger()
        self.logger = logger
        self.phase = phase

    # -- infrastructure ------------------------------------------------------

    def ensure_dataset(self) -> None:
        """Create the working dataset if needed (location + auto-expiration)."""
        dataset_id = f"{self.settings.google_cloud_project}.{self.settings.dataset_id}"
        try:
            self.client.get_dataset(dataset_id)
            return
        except NotFound:
            pass
        dataset = bigquery.Dataset(dataset_id)
        dataset.location = self.settings.bigquery_location
        dataset.default_table_expiration_ms = DEFAULT_TABLE_EXPIRATION_MS
        self.client.create_dataset(dataset, exists_ok=True)
        self._log("ensure_dataset", "completed")

    def destination_has_rows(self, table_id: str) -> bool:
        """True when the destination table already exists and has rows."""
        try:
            table = self.client.get_table(table_id)
        except NotFound:
            return False
        return bool(table.num_rows)

    # -- lifecycle -----------------------------------------------------------

    def estimate_query_bytes(self, query_name: str, sql: str) -> int:
        """Free dry run; logs the estimate to the ledger and runlog."""
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        started = time.monotonic()
        job = self.client.query(
            sql, job_config=job_config, location=self.settings.bigquery_location
        )
        estimated = int(job.total_bytes_processed or 0)
        self.ledger.append(
            phase=self.phase,
            query_name=query_name,
            estimated_bytes=estimated,
            actual_bytes=0,
            runtime_seconds=time.monotonic() - started,
            status=STATUS_DRY_RUN,
        )
        self._log(f"dry-run:{query_name}", "completed", bytes_processed=estimated)
        return estimated

    def execute(self, spec: QuerySpec) -> ExecutionOutcome:
        """Run one plan step with every guard applied, in order.

        Order of operations: idempotent skip check → free dry run → cumulative
        budget check (refuse before execution) → execute with
        ``maximum_bytes_billed`` → ledger + runlog accounting.
        """
        if spec.skip_if_exists and spec.destination and self.destination_has_rows(spec.destination):
            self.ledger.append(
                phase=self.phase,
                query_name=spec.name,
                estimated_bytes=0,
                actual_bytes=0,
                runtime_seconds=0.0,
                status=STATUS_SKIPPED,
            )
            self._log(f"execute:{spec.name}", "skipped")
            return ExecutionOutcome(
                query_name=spec.name, status=STATUS_SKIPPED, estimated_bytes=0, actual_bytes=0
            )

        estimated = self.estimate_query_bytes(spec.name, spec.sql)

        consumed = self.ledger.consumed_bytes(self.phase)
        try:
            assert_within_budget(estimated, consumed, self.settings.bigquery_max_bytes_phase3)
        except BudgetExceededError:
            self.ledger.append(
                phase=self.phase,
                query_name=spec.name,
                estimated_bytes=estimated,
                actual_bytes=0,
                runtime_seconds=0.0,
                status=STATUS_REFUSED,
            )
            self._log(f"execute:{spec.name}", "failed", error_type="BudgetExceededError")
            raise

        job_config = bigquery.QueryJobConfig(
            maximum_bytes_billed=maximum_bytes_billed_for(estimated),
            use_query_cache=False,
        )
        if spec.destination is not None:
            job_config.destination = bigquery.TableReference.from_string(spec.destination)
            if spec.write_disposition is not None:
                job_config.write_disposition = spec.write_disposition

        started = time.monotonic()
        try:
            job = self.client.query(
                spec.sql, job_config=job_config, location=self.settings.bigquery_location
            )
            result = job.result()
            rows = [dict(row) for row in result] if spec.fetch_rows else None
        except Exception as exc:
            self.ledger.append(
                phase=self.phase,
                query_name=spec.name,
                estimated_bytes=estimated,
                actual_bytes=estimated,  # conservative: job may have scanned up to the cap
                runtime_seconds=time.monotonic() - started,
                status=STATUS_ERROR,
            )
            self._log(f"execute:{spec.name}", "failed", error_type=type(exc).__name__)
            raise
        actual = int(job.total_bytes_processed or 0)
        runtime = time.monotonic() - started
        self.ledger.append(
            phase=self.phase,
            query_name=spec.name,
            estimated_bytes=estimated,
            actual_bytes=actual,
            runtime_seconds=runtime,
            status=STATUS_SUCCESS,
        )
        self._log(
            f"execute:{spec.name}",
            "completed",
            bytes_processed=actual,
            duration_seconds=round(runtime, 3),
        )
        return ExecutionOutcome(
            query_name=spec.name,
            status=STATUS_SUCCESS,
            estimated_bytes=estimated,
            actual_bytes=actual,
            rows=rows,
        )

    def _log(self, step: str, status: str, **fields: int | float | str | None) -> None:
        if self.logger is not None:
            self.logger.step(step, status, **fields)
