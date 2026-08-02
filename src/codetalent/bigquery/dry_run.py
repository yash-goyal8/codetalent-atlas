"""Discovery plan construction and pure dry-run pricing (spec section 13).

Builds the ordered Phase 3 query plan (per-month grids, bot audit, human view,
repository rollup, activity filters, contributor extraction, quality checks)
with every statement fully rendered from the configuration contracts, and
prices it without executing anything: :func:`price_plan` only calls the
injected estimator (a free BigQuery dry run) and existence probe, so the module
itself never runs a query. Per the failure policy, a dry-run estimate over
budget fails before execution — enforced by the runner using these estimates.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from codetalent.bigquery import sqlgen
from codetalent.config import AtlasConfig, ConfigError, TaxonomyConfig
from codetalent.settings import Settings

# --- Output bounds (documented decisions, not configuration contracts) -------
#
# These are bounding constants for the local Parquet export funnel, not scoring
# weights or filter thresholds (those all come from config/*.yaml at render
# time). They exist to keep the materialized summary table and the REST fetch
# bounded (spec 5.1 sandbox limits):
#
# * SUMMARY_MIN_HUMAN_CONTRIBUTORS: a repository enters the repository activity
#   summary when it has at least this many unique human contributors OR it
#   matches the domain taxonomy name predicate (with the candidate floor).
# * CANDIDATE_MIN_HUMAN_CONTRIBUTORS / CANDIDATE_MIN_MEANINGFUL_EVENTS: the
#   minimal activity floor for a taxonomy name match to count as a discovered
#   candidate. Repositories below it can never pass the config/repo_filters
#   minimums anyway (those minimums are strictly higher).
#
# Recorded in docs/decisions.md; revisited when Milestone C enrichment lands.
SUMMARY_MIN_HUMAN_CONTRIBUTORS = 2
CANDIDATE_MIN_HUMAN_CONTRIBUTORS = 1
CANDIDATE_MIN_MEANINGFUL_EVENTS = 1

PROFILE_TEMPLATE = "00_profile_tables.sql"
EXTRACT_TEMPLATE = "01_extract_events.sql"
BOT_AUDIT_TEMPLATE = "02_remove_bots.sql"
AGGREGATE_TEMPLATE = "03_aggregate_repositories.sql"
FILTERS_TEMPLATE = "04_apply_activity_filters.sql"
CONTRIBUTOR_TEMPLATE = "05_extract_contributor_activity.sql"
QUALITY_TEMPLATE = "06_quality_checks.sql"


@dataclass(frozen=True)
class QuerySpec:
    """One fully rendered query in the discovery plan."""

    name: str
    sql: str
    destination: str | None = None
    skip_if_exists: bool = False
    write_disposition: str | None = None
    fetch_rows: bool = False


@dataclass(frozen=True)
class QueryEstimate:
    """Dry-run pricing outcome for one plan entry."""

    name: str
    estimated_bytes: int | None
    will_skip: bool = False
    note: str | None = None


@dataclass(frozen=True)
class PlanPricing:
    """Aggregate pricing for a plan; planned bytes exclude skipped queries."""

    estimates: tuple[QueryEstimate, ...]
    planned_bytes: int
    unpriced: tuple[str, ...]


def months_in_window(start: date, end: date) -> list[str]:
    """GH Archive month suffixes (YYYYMM) covered by [start, end]."""
    if start > end:
        raise ConfigError(f"window start {start} is after end {end}")
    months: list[str] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year:04d}{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def _project_and_dataset(settings: Settings) -> tuple[str, str]:
    if not settings.google_cloud_project:
        raise ConfigError(
            "GOOGLE_CLOUD_PROJECT is not set. Add it to your local .env "
            "(see .env.example); the BigQuery Sandbox project must have no billing."
        )
    project = sqlgen.validate_identifier(settings.google_cloud_project, kind="project")
    dataset = sqlgen.validate_identifier(settings.dataset_id, kind="dataset")
    return project, dataset


def _taxonomy(config: AtlasConfig, domain_id: str) -> TaxonomyConfig:
    if domain_id not in config.taxonomies:
        raise ConfigError(
            f"domain {domain_id!r} has no taxonomy configured; "
            f"available: {sorted(config.taxonomies)}"
        )
    return config.taxonomies[domain_id]


def build_discovery_plan(
    *,
    config: AtlasConfig,
    settings: Settings,
    domain_id: str,
    start: date,
    end: date,
    sql_dir: Path = sqlgen.DEFAULT_SQL_DIR,
) -> list[QuerySpec]:
    """Render the ordered Phase 3 plan; raises ConfigError on bad inputs."""
    project, dataset = _project_and_dataset(settings)
    taxonomy = _taxonomy(config, domain_id)
    sqlgen.validate_identifier(domain_id, kind="domain id")
    months = months_in_window(start, end)
    weight_params = sqlgen.event_weight_params(config.scoring.event_weights)
    minimums = config.repo_filters.minimums

    union = sqlgen.grid_union(project, dataset, months)
    repo_activity_table = sqlgen.REPO_ACTIVITY_TABLE_FORMAT.format(domain_id=domain_id)
    repo_discovery_table = sqlgen.REPO_DISCOVERY_TABLE_FORMAT.format(domain_id=domain_id)
    contributor_table = sqlgen.CONTRIBUTOR_TABLE_FORMAT.format(domain_id=domain_id)

    plan: list[QuerySpec] = []

    extract_sql = sqlgen.load_statements(sql_dir / EXTRACT_TEMPLATE)["extract_events"]
    bot_case = sqlgen.bot_pattern_case(config.bot_patterns)
    for month in months:
        plan.append(
            QuerySpec(
                name=f"extract_events_{month}",
                sql=sqlgen.render_statement(
                    extract_sql,
                    {"month": sqlgen.validate_month(month), "bot_pattern_case": bot_case},
                ),
                destination=sqlgen.grid_table_id(project, dataset, month),
                # The only expensive scans in the pipeline: resume semantics,
                # never re-run a month grid that already exists with rows.
                skip_if_exists=True,
                write_disposition="WRITE_EMPTY",
            )
        )

    bot_statements = sqlgen.load_statements(sql_dir / BOT_AUDIT_TEMPLATE)
    plan.append(
        QuerySpec(
            name="bot_exclusion_audit",
            sql=sqlgen.render_statement(
                bot_statements["bot_exclusion_audit"], {"grid_union": union}
            ),
            destination=f"{project}.{dataset}.{sqlgen.BOT_AUDIT_TABLE}",
            # Cheap grid-only scan: refresh on every run.
            write_disposition="WRITE_TRUNCATE",
        )
    )
    plan.append(
        QuerySpec(
            name="human_grid_view",
            sql=sqlgen.render_statement(
                bot_statements["human_grid_view"],
                {
                    "project": project,
                    "dataset": dataset,
                    "human_view": sqlgen.HUMAN_GRID_VIEW,
                    "grid_union": union,
                },
            ),
            # DDL (CREATE OR REPLACE VIEW): no destination, inherently idempotent.
        )
    )

    aggregate_sql = sqlgen.load_statements(sql_dir / AGGREGATE_TEMPLATE)["aggregate_repositories"]
    plan.append(
        QuerySpec(
            name=f"aggregate_repositories_{domain_id}",
            sql=sqlgen.render_statement(
                aggregate_sql,
                {
                    "grid_union": union,
                    "taxonomy_predicate": sqlgen.taxonomy_match_predicate(
                        taxonomy, column="r.repo_name"
                    ),
                    "summary_min_human_contributors": str(SUMMARY_MIN_HUMAN_CONTRIBUTORS),
                    "candidate_min_human_contributors": str(CANDIDATE_MIN_HUMAN_CONTRIBUTORS),
                    **weight_params,
                },
            ),
            destination=f"{project}.{dataset}.{repo_activity_table}",
            write_disposition="WRITE_TRUNCATE",
        )
    )

    filters_sql = sqlgen.load_statements(sql_dir / FILTERS_TEMPLATE)["apply_activity_filters"]
    plan.append(
        QuerySpec(
            name=f"apply_activity_filters_{domain_id}",
            sql=sqlgen.render_statement(
                filters_sql,
                {
                    "project": project,
                    "dataset": dataset,
                    "repo_activity_table": repo_activity_table,
                    "min_unique_human_contributors": str(minimums.unique_human_contributors),
                    "min_meaningful_events": str(minimums.meaningful_events),
                    "min_pull_requests_or_reviews": str(minimums.pull_requests_or_reviews),
                    "min_active_months": str(minimums.active_months),
                    "candidate_min_human_contributors": str(CANDIDATE_MIN_HUMAN_CONTRIBUTORS),
                    "candidate_min_meaningful_events": str(CANDIDATE_MIN_MEANINGFUL_EVENTS),
                },
            ),
            destination=f"{project}.{dataset}.{repo_discovery_table}",
            write_disposition="WRITE_TRUNCATE",
        )
    )

    contributor_sql = sqlgen.load_statements(sql_dir / CONTRIBUTOR_TEMPLATE)[
        "extract_contributor_activity"
    ]
    plan.append(
        QuerySpec(
            name=f"extract_contributor_activity_{domain_id}",
            sql=sqlgen.render_statement(
                contributor_sql,
                {
                    "grid_union": union,
                    "project": project,
                    "dataset": dataset,
                    "repo_discovery_table": repo_discovery_table,
                    "domain_id_literal": sqlgen.sql_string_literal(domain_id),
                    **weight_params,
                },
            ),
            destination=f"{project}.{dataset}.{contributor_table}",
            write_disposition="WRITE_TRUNCATE",
        )
    )

    quality_sql = sqlgen.load_statements(sql_dir / QUALITY_TEMPLATE)["quality_checks"]
    plan.append(
        QuerySpec(
            name="quality_checks",
            sql=sqlgen.render_statement(
                quality_sql,
                {
                    "project": project,
                    "dataset": dataset,
                    "repo_discovery_table": repo_discovery_table,
                    "contributor_table": contributor_table,
                    "grid_duplicate_total": sqlgen.grid_duplicate_total(project, dataset, months),
                    "window_start": sqlgen.validate_iso_date(start.isoformat()),
                    "window_end": sqlgen.validate_iso_date(end.isoformat()),
                },
            ),
            fetch_rows=True,
        )
    )
    return plan


def build_profile_plan(
    months: list[str], *, sql_dir: Path = sqlgen.DEFAULT_SQL_DIR
) -> list[QuerySpec]:
    """DRY-RUN-ONLY column-group profiling queries (never executed)."""
    statements = sqlgen.load_statements(sql_dir / PROFILE_TEMPLATE)
    return [
        QuerySpec(
            name=f"{statement_name}_{month}",
            sql=sqlgen.render_statement(sql, {"month": sqlgen.validate_month(month)}),
        )
        for month in months
        for statement_name, sql in statements.items()
    ]


def price_plan(
    plan: list[QuerySpec],
    *,
    estimate_bytes: Callable[[QuerySpec], int],
    destination_has_rows: Callable[[str], bool],
) -> PlanPricing:
    """Price a plan without executing it.

    ``estimate_bytes`` performs the free BigQuery dry run (and may record it in
    the usage ledger); a ``google.api_core.exceptions.NotFound`` from it marks
    the query unpriced — its inputs are tables an earlier plan entry creates,
    so it is re-priced and budget-guarded at execution time by the runner.
    Queries whose destination already has rows are shown but excluded from the
    planned total (idempotent skip).
    """
    from google.api_core.exceptions import NotFound

    estimates: list[QueryEstimate] = []
    planned = 0
    unpriced: list[str] = []
    for spec in plan:
        will_skip = bool(
            spec.skip_if_exists and spec.destination and destination_has_rows(spec.destination)
        )
        try:
            estimated: int | None = estimate_bytes(spec)
            note = None
        except NotFound as exc:
            estimated = None
            detail = getattr(exc, "message", None) or "not found"
            note = f"unpriced until earlier plan tables exist ({detail})"
            unpriced.append(spec.name)
        if estimated is not None and not will_skip:
            planned += estimated
        estimates.append(
            QueryEstimate(name=spec.name, estimated_bytes=estimated, will_skip=will_skip, note=note)
        )
    return PlanPricing(estimates=tuple(estimates), planned_bytes=planned, unpriced=tuple(unpriced))
