"""REST-only export of discovery tables to local Parquet (spec 5.1, 13).

Sandbox tables expire, so every permanent result is fetched over the plain
BigQuery REST API — ``list_rows(...).to_arrow(create_bqstorage_client=False)``,
never the Storage Read API, extract jobs, or GCS — and written under
``data/interim/`` at deterministic paths.

Output bounds (documented in codetalent.bigquery.dry_run and docs/decisions.md):

* ``repository_activity_summary.parquet`` — every row of the materialized
  discovery table; the table itself is already bounded to repositories with at
  least SUMMARY_MIN_HUMAN_CONTRIBUTORS unique human contributors OR a taxonomy
  name match with the candidate floor, which keeps this REST fetch bounded.
* ``<domain>_repository_candidates.parquet`` — only the discovered-candidate
  rows (discovery_status 'accepted' or 'excluded'); excluded rows keep their
  exclusion_reason for auditability.
* ``contributor_activity.parquet`` — human actors in activity-passed
  ('accepted') repositories only. The spec 9.4 ``subdomains`` field cannot be
  known before Milestone C classification, so it is written as an empty list.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from google.cloud import bigquery

from codetalent.bigquery import sqlgen
from codetalent.schemas import ContributorActivity, RepositoryActivitySummary

INTERIM_DIR = Path("data/interim")

# Spec 9.1 / 9.4 field names in declaration order — the Parquet column contract.
SUMMARY_COLUMNS: tuple[str, ...] = tuple(RepositoryActivitySummary.model_fields)
CONTRIBUTOR_COLUMNS: tuple[str, ...] = tuple(ContributorActivity.model_fields)


class ExportError(RuntimeError):
    """A discovery table is missing columns the export contract requires."""


def summary_parquet_path(interim_dir: Path = INTERIM_DIR) -> Path:
    return interim_dir / "repository_activity_summary.parquet"


def candidates_parquet_path(domain_id: str, interim_dir: Path = INTERIM_DIR) -> Path:
    return interim_dir / f"{domain_id}_repository_candidates.parquet"


def contributor_parquet_path(interim_dir: Path = INTERIM_DIR) -> Path:
    return interim_dir / "contributor_activity.parquet"


def fetch_table_arrow(client: bigquery.Client, table_id: str, columns: tuple[str, ...]) -> pa.Table:
    """Fetch selected columns of a table via the REST API into pyarrow."""
    table = client.get_table(table_id)
    wanted = set(columns)
    selected_fields = [field for field in table.schema if field.name in wanted]
    missing = wanted - {field.name for field in selected_fields}
    if missing:
        raise ExportError(f"{table_id} is missing required columns: {sorted(missing)}")
    row_iterator = client.list_rows(table, selected_fields=selected_fields)
    # REST-only contract: never construct a BigQuery Storage client.
    arrow = row_iterator.to_arrow(create_bqstorage_client=False)
    return arrow.select(list(columns))


def _write_parquet(table: pa.Table, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


@dataclass(frozen=True)
class DiscoveryExport:
    """Paths and funnel counts of one export run (only what actually ran)."""

    summary_path: Path
    candidates_path: Path
    contributor_path: Path
    summary_rows: int
    discovered_candidates: int
    activity_passed: int
    contributor_rows: int


def export_discovery_outputs(
    client: bigquery.Client,
    *,
    repo_discovery_table: str,
    contributor_table: str,
    domain_id: str,
    interim_dir: Path = INTERIM_DIR,
) -> DiscoveryExport:
    """Write the three Phase 3 Parquet outputs and return funnel counts."""
    summary = fetch_table_arrow(client, repo_discovery_table, SUMMARY_COLUMNS)
    summary_path = _write_parquet(summary, summary_parquet_path(interim_dir))

    status = summary.column("discovery_status")
    candidate_mask = pc.is_in(status, value_set=pa.array(sqlgen.CANDIDATE_STATUSES))
    candidates = summary.filter(candidate_mask)
    candidates_path = _write_parquet(candidates, candidates_parquet_path(domain_id, interim_dir))
    activity_passed = int(
        pc.sum(pc.cast(pc.equal(status, sqlgen.STATUS_ACCEPTED), pa.int64())).as_py() or 0
    )

    fetched_contributor_columns = tuple(
        column for column in CONTRIBUTOR_COLUMNS if column != "subdomains"
    )
    contributors = fetch_table_arrow(client, contributor_table, fetched_contributor_columns)
    # subdomains (spec 9.4) are assigned by Milestone C classification; an
    # empty list records "no labels assigned yet" without fabricating values.
    empty_subdomains = pa.array([[]] * contributors.num_rows, type=pa.list_(pa.string()))
    contributors = contributors.append_column("subdomains", empty_subdomains)
    contributors = contributors.select(list(CONTRIBUTOR_COLUMNS))
    contributor_path = _write_parquet(contributors, contributor_parquet_path(interim_dir))

    return DiscoveryExport(
        summary_path=summary_path,
        candidates_path=candidates_path,
        contributor_path=contributor_path,
        summary_rows=summary.num_rows,
        discovered_candidates=candidates.num_rows,
        activity_passed=activity_passed,
        contributor_rows=contributors.num_rows,
    )
