"""Milestone C repository enrichment orchestration (spec sections 9.2, 14, 26).

Reads the discovery worklist (``discovery_status == "accepted"`` rows of the
repository activity summary, sorted by ``repo_name`` for determinism), skips
records already completed in the checkpoint, batches the remainder into
alias-based GraphQL queries (cache-first), parses responses into spec 9.2
:class:`~codetalent.schemas.RepositoryMetadata` rows, and after every batch:

* rewrites ``data/interim/repository_metadata.parquet`` atomically (temp file
  + rename, deduplicated by ``repo_name`` keeping the latest fetch);
* persists the checkpoint (completed IDs, failed IDs with reasons and retry
  counts, last rate-limit state, current batch size);
* appends one row per request to ``reports/enrichment_usage.csv`` with the
  existing header preserved exactly;
* emits one structured runlog event.

Failure policy: deleted/renamed repositories (``NOT_FOUND``) are quarantined
permanently in the checkpoint's failure list and never retried; they do not
count toward the stop-the-run error rate because they are expected transitions
(spec section 14 acceptance criteria exclude them). Any other failure counts
toward the error rate, and once at least ``error_rate_min_sample`` records have
been processed a rate above ``max_error_rate`` (default 1%) stops the run with
the checkpoint preserved (spec section 26).

Batch-size adaptation (spec section 14): batches start at 10 repositories per
request; when a measured batch costs more than 1 rate-limit point per ~10 repos
or its response exceeds 1 MiB, the size resets to 10; otherwise it may step up
to 25 and then 50, never higher. The chosen size persists in the checkpoint.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from codetalent.github.cache import ResponseCache, repository_batch_hash
from codetalent.github.checkpoints import PERMANENT_FAILURE_REASONS, CheckpointStore
from codetalent.github.graphql_client import (
    TOKEN_SETUP_INSTRUCTIONS,
    GitHubAuthenticationError,
    GraphQLClient,
    GraphQLRequestError,
    SecondaryRateLimitError,
)
from codetalent.github.query_builder import (
    REPO_QUERY_VERSION,
    REPO_QUERY_VERSION_LIGHT,
    build_repository_batch_query,
)
from codetalent.github.rate_limit import DEFAULT_RATE_LIMIT_FLOOR
from codetalent.runlog import RunLogger
from codetalent.schemas import RepositoryMetadata
from codetalent.settings import Settings, load_settings

DEFAULT_INPUT_PATH = Path("data/interim/repository_activity_summary.parquet")
METADATA_PATH = Path("data/interim/repository_metadata.parquet")
CHECKPOINT_PATH = Path("data/interim/checkpoints/repositories.json")
CACHE_DIR = Path("data/cache/github/graphql/repositories")
USAGE_REPORT_PATH = Path("reports/enrichment_usage.csv")

#: reports/enrichment_usage.csv header — must match the existing file exactly.
USAGE_HEADER: tuple[str, ...] = (
    "timestamp",
    "resource_type",
    "batch_size",
    "query_cost",
    "remaining",
    "reset_at",
    "status",
    "retries",
    "cache_hit",
)

RESOURCE_TYPE_REPOSITORIES = "graphql_repositories"
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_SECONDARY_LIMIT = "secondary_limit"
STATUS_AUTH_ERROR = "auth_error"

INITIAL_BATCH_SIZE = 10
# Growth is capped at 25: the 2026-08-02 live run showed 50-alias batches with
# eight object() expressions each fail consistently (complexity/timeout), while
# 25 costs a single point per request — the ceiling buys nothing but risk.
BATCH_SIZE_STEPS: tuple[int, ...] = (10, 25)
MAX_RESPONSE_BYTES_FOR_GROWTH = 1024 * 1024  # 1 MiB
MAX_COST_PER_REPO_FOR_GROWTH = 1 / 10  # 1 rate-limit point per ~10 repositories

_METADATA_COLUMNS: tuple[str, ...] = tuple(RepositoryMetadata.model_fields)
_UTC_DATETIME = pl.Datetime(time_unit="us", time_zone="UTC")
_METADATA_SCHEMA: dict[str, pl.DataType] = {
    "repo_name": pl.String(),
    "description": pl.String(),
    "is_fork": pl.Boolean(),
    "is_archived": pl.Boolean(),
    "is_disabled": pl.Boolean(),
    "primary_language": pl.String(),
    "topics": pl.List(pl.String()),
    "stargazer_count": pl.Int64(),
    "fork_count": pl.Int64(),
    "license_spdx_id": pl.String(),
    "pushed_at": _UTC_DATETIME,
    "updated_at": _UTC_DATETIME,
    "release_count": pl.Int64(),
    "issue_count": pl.Int64(),
    "pull_request_count": pl.Int64(),
    "has_readme": pl.Boolean(),
    "has_contributing": pl.Boolean(),
    "has_code_of_conduct": pl.Boolean(),
    "has_ci": pl.Boolean(),
    "has_tests_signal": pl.Boolean(),
    "graphql_fetched_at": _UTC_DATETIME,
}


class WorklistError(RuntimeError):
    """The enrichment worklist is missing or malformed."""


class ErrorRateExceededError(RuntimeError):
    """Unexpected failure rate exceeded the configured maximum (spec section 26)."""


class LedgerFormatError(RuntimeError):
    """reports/enrichment_usage.csv does not match the required header."""


class EnrichmentUsageLedger:
    """Append-only accounting of every enrichment request (API-safety rule 5)."""

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
        resource_type: str,
        batch_size: int,
        query_cost: int,
        remaining: int | None,
        reset_at: str,
        status: str,
        retries: int,
        cache_hit: bool,
    ) -> None:
        """Append one row, creating the file (or validating its header) first."""
        self._check_or_create_header()
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                [
                    _utc_timestamp(),
                    resource_type,
                    batch_size,
                    query_cost,
                    "" if remaining is None else remaining,
                    reset_at,
                    status,
                    retries,
                    "true" if cache_hit else "false",
                ]
            )


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_worklist(input_path: Path) -> list[str]:
    """Accepted repository names from the activity summary, sorted and unique."""
    if not input_path.exists():
        raise WorklistError(
            f"worklist not found: {input_path} — run `codetalent bq discover` first "
            "or pass --input explicitly"
        )
    frame = pl.read_parquet(input_path, columns=["repo_name", "discovery_status"])
    accepted = frame.filter(pl.col("discovery_status") == "accepted")
    return sorted(set(accepted.get_column("repo_name").to_list()))


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _object_present(node: Mapping[str, Any], *aliases: str) -> bool | None:
    """True/False when the content-signal aliases were queried; None when the
    light (bulk) query omitted them entirely."""
    if all(alias not in node for alias in aliases):
        return None
    return any(node.get(alias) is not None for alias in aliases)


def repository_metadata_from_node(
    repo_name: str, node: Mapping[str, Any], fetched_at: datetime
) -> RepositoryMetadata:
    """Map one GraphQL repository node onto the spec 9.2 metadata model.

    ``repo_name`` stays the worklist name (the discovery join key) even when
    the repository was renamed and GraphQL reports a new ``nameWithOwner``.
    Content-presence booleans are True/False when the full query ran, and None
    for light (bulk) fetches — the content pass over the qualified shortlist
    fills them in (spec 14: content checks are for a small shortlist only).
    """
    topics_nodes = (node.get("repositoryTopics") or {}).get("nodes") or []
    topics = [
        entry["topic"]["name"]
        for entry in topics_nodes
        if isinstance(entry, dict) and entry.get("topic")
    ]
    return RepositoryMetadata(
        repo_name=repo_name,
        description=node.get("description"),
        is_fork=bool(node["isFork"]),
        is_archived=bool(node["isArchived"]),
        is_disabled=bool(node["isDisabled"]),
        primary_language=(node.get("primaryLanguage") or {}).get("name"),
        topics=topics,
        stargazer_count=int(node["stargazerCount"]),
        fork_count=int(node["forkCount"]),
        license_spdx_id=(node.get("licenseInfo") or {}).get("spdxId"),
        pushed_at=_parse_datetime(node.get("pushedAt")),
        updated_at=_parse_datetime(node.get("updatedAt")),
        release_count=int((node.get("releases") or {}).get("totalCount", 0)),
        issue_count=int((node.get("issues") or {}).get("totalCount", 0)),
        pull_request_count=int((node.get("pullRequests") or {}).get("totalCount", 0)),
        has_readme=_object_present(node, "readmeMd", "readmeRst", "readmeLower"),
        has_contributing=_object_present(node, "contributing"),
        has_code_of_conduct=_object_present(node, "codeOfConduct"),
        has_ci=_object_present(node, "ciWorkflows"),
        has_tests_signal=_object_present(node, "testsDir", "testDir"),
        graphql_fetched_at=fetched_at,
    )


def write_metadata_atomic(rows: Sequence[RepositoryMetadata], path: Path) -> int:
    """Merge rows into the metadata Parquet atomically; return the row count.

    Existing rows are kept, duplicates by ``repo_name`` resolve to the latest
    ``graphql_fetched_at``, and the file is replaced via temp file + rename so
    a crash mid-write never corrupts previously persisted data.
    """
    new_frame = pl.DataFrame(
        [row.model_dump() for row in rows], schema=_METADATA_SCHEMA, orient="row"
    ).select(_METADATA_COLUMNS)
    frames = [new_frame]
    if path.exists():
        frames.insert(0, pl.read_parquet(path).select(_METADATA_COLUMNS))
    combined = (
        pl.concat(frames, how="vertical")
        .sort("graphql_fetched_at")
        .unique(subset=["repo_name"], keep="last", maintain_order=True)
        .sort("repo_name")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    combined.write_parquet(tmp)
    os.replace(tmp, path)
    return combined.height


def next_batch_size(current: int, *, cost: int | None, response_bytes: int, batch_len: int) -> int:
    """Adapt the batch size from one measured (non-cached) batch outcome.

    Partial tail batches (fewer repositories than the current size) are not
    representative — every GraphQL query costs at least 1 point, so a tiny
    remainder batch always looks "expensive" per repository — and never change
    the size.
    """
    if batch_len <= 0 or cost is None or batch_len < current:
        return current
    too_expensive = cost > batch_len * MAX_COST_PER_REPO_FOR_GROWTH
    too_large = response_bytes > MAX_RESPONSE_BYTES_FOR_GROWTH
    if too_expensive or too_large:
        return INITIAL_BATCH_SIZE
    for step in BATCH_SIZE_STEPS:
        if step > current:
            return step
    return current


@dataclass(frozen=True)
class EnrichmentReport:
    """Summary of one enrichment run for CLI display and tests."""

    worklist_total: int
    already_completed: int
    attempted: int
    succeeded: int
    failed: int
    cache_hits: int
    batch_size: int
    total_rows: int
    output_path: Path
    #: Non-permanent failures at the retry cap (repo -> latest reason). These
    #: are silently skipped by every future run at the same cap, so the CLI
    #: must surface them; re-run with a higher --max-failure-retries to retry.
    exhausted_failures: dict[str, str] = field(default_factory=dict)


def enrich_repositories(
    *,
    settings: Settings | None = None,
    input_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = METADATA_PATH,
    checkpoint_path: Path = CHECKPOINT_PATH,
    cache_dir: Path = CACHE_DIR,
    usage_report_path: Path = USAGE_REPORT_PATH,
    limit: int | None = None,
    client: GraphQLClient | None = None,
    logger: RunLogger | None = None,
    rate_limit_floor: int = DEFAULT_RATE_LIMIT_FLOOR,
    max_failure_retries: int = 3,
    max_error_rate: float = 0.01,
    error_rate_min_sample: int = 100,
    content_signals: bool = False,
) -> EnrichmentReport:
    """Run resumable, cache-first repository enrichment over the worklist.

    ``limit`` caps how many not-yet-completed repositories this run attempts
    (smoke runs); completed records are always skipped first, so a limited run
    still never refetches anything.
    """
    log = logger if logger is not None else RunLogger("phase4-enrich-repos")
    worklist = load_worklist(input_path)
    checkpoint = CheckpointStore(checkpoint_path, default_batch_size=INITIAL_BATCH_SIZE)
    cache = ResponseCache(cache_dir)
    ledger = EnrichmentUsageLedger(usage_report_path)

    completed = checkpoint.completed_ids()
    failures = checkpoint.failed_records()
    retriable = set(checkpoint.retriable_failures(max_retries=max_failure_retries))
    pending = [
        name
        for name in worklist
        if name not in completed and (name not in failures or name in retriable)
    ]
    already_completed = len([name for name in worklist if name in completed])
    if limit is not None:
        pending = pending[: max(limit, 0)]

    owns_client = client is None
    if client is None:
        if settings is None:
            settings = load_settings()
        token = settings.github_token
        if token is None:
            raise GitHubAuthenticationError("GITHUB_TOKEN is not set.\n" + TOKEN_SETUP_INSTRUCTIONS)
        client = GraphQLClient(token.get_secret_value(), rate_limit_floor=rate_limit_floor)
    if client.last_rate_limit is None and checkpoint.last_rate_limit is not None:
        # Resume rate-limit continuity: a stale state sleeps ~0s, a fresh one
        # below the floor pauses before the very first request of this run.
        client.last_rate_limit = checkpoint.last_rate_limit

    batch_size = checkpoint.batch_size
    attempted = succeeded = failed = cache_hits = 0
    unexpected_failures = 0
    total_rows = 0

    log.step(
        "worklist",
        "completed",
        records_in=len(worklist),
        records_out=len(pending),
        cache_hits=already_completed,
    )

    try:
        while pending:
            batch = pending[:batch_size]
            pending = pending[batch_size:]
            built = build_repository_batch_query(batch, include_content_signals=content_signals)
            batch_hash = repository_batch_hash(
                batch,
                query_version=REPO_QUERY_VERSION if content_signals else REPO_QUERY_VERSION_LIGHT,
            )

            cached = cache.get(batch_hash)
            cache_hit = cached is not None
            if cached is not None:
                data: dict[str, Any] = cached.get("data") or {}
                errors: list[dict[str, Any]] = list(cached.get("errors") or [])
                cost: int | None = 0
                response_bytes = 0
                retries = 0
                rate_state = client.last_rate_limit
            else:
                try:
                    result = client.execute(built.query)
                except GitHubAuthenticationError:
                    # The request was issued and spent; account for it (rule 5)
                    # before the immediate stop with setup instructions.
                    ledger.append(
                        resource_type=RESOURCE_TYPE_REPOSITORIES,
                        batch_size=len(batch),
                        query_cost=0,
                        remaining=None,
                        reset_at="",
                        status=STATUS_AUTH_ERROR,
                        retries=0,
                        cache_hit=False,
                    )
                    log.step("enrich-batch", "failed", error_type="GitHubAuthenticationError")
                    raise
                except SecondaryRateLimitError:
                    ledger.append(
                        resource_type=RESOURCE_TYPE_REPOSITORIES,
                        batch_size=len(batch),
                        query_cost=0,
                        remaining=None,
                        reset_at="",
                        status=STATUS_SECONDARY_LIMIT,
                        retries=0,
                        cache_hit=False,
                    )
                    log.step("enrich-batch", "failed", error_type="SecondaryRateLimitError")
                    raise
                except GraphQLRequestError as exc:
                    # Whole-request failure after retries: quarantine the batch
                    # and continue; the error-rate guard stops a broken run.
                    ledger.append(
                        resource_type=RESOURCE_TYPE_REPOSITORIES,
                        batch_size=len(batch),
                        query_cost=0,
                        remaining=None,
                        reset_at="",
                        status=STATUS_ERROR,
                        retries=exc.retries,
                        cache_hit=False,
                    )
                    # A whole-request failure with multiple repositories is
                    # usually one poison repository (or the batch shape), not
                    # all of them: requeue the batch and halve the slice size
                    # so retries bisect toward the culprit. Only a failing
                    # SINGLETON is quarantined and counted toward the error
                    # rate — so the 1% guard measures true per-repo failures.
                    if len(batch) > 1:
                        pending = batch + pending
                        batch_size = max(1, len(batch) // 2)
                        log.step(
                            "enrich-batch",
                            "bisect",
                            records_in=len(batch),
                            error_type=type(exc).__name__,
                        )
                        continue
                    reason = f"REQUEST_ERROR:{type(exc).__name__}"
                    checkpoint.record_batch([], dict.fromkeys(batch, reason), batch_size=batch_size)
                    attempted += len(batch)
                    failed += len(batch)
                    unexpected_failures += len(batch)
                    log.step(
                        "enrich-batch",
                        "failed",
                        records_in=len(batch),
                        error_type=type(exc).__name__,
                    )
                    _check_error_rate(
                        unexpected_failures, attempted, max_error_rate, error_rate_min_sample
                    )
                    continue
                data = result.data
                errors = result.errors
                cost = result.rate_limit.last_cost if result.rate_limit is not None else None
                response_bytes = result.response_bytes
                retries = result.retries
                rate_state = result.rate_limit
                cache.put(batch_hash, {"data": data, "errors": errors})

            fetched_at = datetime.now(UTC)
            error_by_alias: dict[str, dict[str, Any]] = {}
            for error in errors:
                path = error.get("path") or []
                if path:
                    error_by_alias[str(path[0])] = error

            batch_rows: list[RepositoryMetadata] = []
            batch_failures: dict[str, str] = {}
            for alias, repo_name in built.alias_to_repo.items():
                node = data.get(alias)
                if not isinstance(node, dict):
                    error = error_by_alias.get(alias, {})
                    reason = str(error.get("type") or error.get("message") or "MISSING")[:200]
                    batch_failures[repo_name] = reason
                    if reason not in PERMANENT_FAILURE_REASONS:
                        unexpected_failures += 1
                    continue
                try:
                    batch_rows.append(repository_metadata_from_node(repo_name, node, fetched_at))
                except Exception as exc:  # malformed node: quarantine, continue
                    batch_failures[repo_name] = f"PARSE_ERROR:{type(exc).__name__}"
                    unexpected_failures += 1

            if batch_rows:
                total_rows = write_metadata_atomic(batch_rows, output_path)
            if not cache_hit:
                batch_size = next_batch_size(
                    batch_size, cost=cost, response_bytes=response_bytes, batch_len=len(batch)
                )
            checkpoint.record_batch(
                [row.repo_name for row in batch_rows],
                batch_failures,
                rate_limit=rate_state,
                batch_size=batch_size,
            )
            ledger.append(
                resource_type=RESOURCE_TYPE_REPOSITORIES,
                batch_size=len(batch),
                query_cost=cost if cost is not None else 0,
                remaining=rate_state.remaining if rate_state is not None else None,
                reset_at=(
                    rate_state.reset_at.isoformat()
                    if rate_state is not None and rate_state.reset_at is not None
                    else ""
                ),
                status=STATUS_SUCCESS,
                retries=retries,
                cache_hit=cache_hit,
            )
            attempted += len(batch)
            succeeded += len(batch_rows)
            failed += len(batch_failures)
            cache_hits += 1 if cache_hit else 0
            log.step(
                "enrich-batch",
                "completed",
                records_in=len(batch),
                records_out=len(batch_rows),
                cache_hits=1 if cache_hit else 0,
                api_cost=float(cost) if cost is not None else None,
            )
            _check_error_rate(unexpected_failures, attempted, max_error_rate, error_rate_min_sample)
    finally:
        if owns_client:
            client.close()

    if total_rows == 0 and output_path.exists():
        total_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()

    # Non-permanent failures at the retry cap are excluded from every future
    # run at this cap; surface them so "done" is distinguishable from "done
    # except N silently abandoned records".
    worklist_set = set(worklist)
    exhausted_failures = {
        name: record.reason
        for name, record in sorted(checkpoint.failed_records().items())
        if name in worklist_set
        and record.reason not in PERMANENT_FAILURE_REASONS
        and record.retries >= max_failure_retries
    }

    log.step(
        "enrich-repos",
        "completed",
        records_in=len(worklist),
        records_out=succeeded,
        cache_hits=cache_hits,
    )
    return EnrichmentReport(
        worklist_total=len(worklist),
        already_completed=already_completed,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        cache_hits=cache_hits,
        batch_size=batch_size,
        total_rows=total_rows,
        output_path=output_path,
        exhausted_failures=exhausted_failures,
    )


def _check_error_rate(
    unexpected_failures: int, attempted: int, max_error_rate: float, min_sample: int
) -> None:
    if attempted >= min_sample and attempted > 0:
        rate = unexpected_failures / attempted
        if rate > max_error_rate:
            raise ErrorRateExceededError(
                f"unexpected failure rate {rate:.2%} over {attempted} records exceeds "
                f"{max_error_rate:.2%}; stopping with the checkpoint preserved "
                "(deleted/renamed NOT_FOUND repositories are excluded from this rate)"
            )
