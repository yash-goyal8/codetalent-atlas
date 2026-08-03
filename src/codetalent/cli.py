"""Typer CLI wired to the spec section 24 command surface.

Commands that belong to later milestones print a one-line message naming the
milestone that implements them and exit with code 2. ``validate all`` and
``pipeline pilot`` already run the real local stages that exist today
(configuration validation and the public-data privacy scan).
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from google.api_core.exceptions import Forbidden, NotFound, Unauthorized
from google.cloud import bigquery

from codetalent import __version__
from codetalent.bigquery import dry_run as bq_plan
from codetalent.bigquery import export as bq_export
from codetalent.bigquery import runner as bq_runner
from codetalent.bigquery import sqlgen
from codetalent.config import DEFAULT_CONFIG_DIR, AtlasConfig, ConfigError, load_all
from codetalent.runlog import RunLogger
from codetalent.settings import Settings, load_settings
from codetalent.validation.privacy import DEFAULT_PUBLIC_DIRS, scan_public_data

app = typer.Typer(
    name="codetalent",
    help="CodeTalent Atlas pipeline: discover, enrich, classify, score, validate, publish.",
    no_args_is_help=True,
)

bq_app = typer.Typer(help="BigQuery discovery over GH Archive.", no_args_is_help=True)
github_app = typer.Typer(help="GitHub GraphQL/REST enrichment.", no_args_is_help=True)
classify_app = typer.Typer(help="Deterministic repository classification.", no_args_is_help=True)
locations_app = typer.Typer(help="Offline location normalization.", no_args_is_help=True)
score_app = typer.Typer(
    help="Repository, contributor, and geography scoring.", no_args_is_help=True
)
validate_app = typer.Typer(help="Data quality, privacy, and bias validation.", no_args_is_help=True)
publish_app = typer.Typer(help="Aggregate-only static web data publishing.", no_args_is_help=True)
pipeline_app = typer.Typer(help="End-to-end pipeline orchestration.", no_args_is_help=True)

app.add_typer(bq_app, name="bq")
app.add_typer(github_app, name="github")
app.add_typer(classify_app, name="classify")
app.add_typer(locations_app, name="locations")
app.add_typer(score_app, name="score")
app.add_typer(validate_app, name="validate")
app.add_typer(publish_app, name="publish")
app.add_typer(pipeline_app, name="pipeline")

_MILESTONES = {
    "B": "BigQuery discovery",
    "C": "repository enrichment and classification",
    "D": "user enrichment and location normalization",
    "E": "scoring and validation",
    "F": "static web data publishing",
}

StartOpt = Annotated[str, typer.Option("--start", help="Window start date (YYYY-MM-DD).")]
EndOpt = Annotated[str, typer.Option("--end", help="Window end date (YYYY-MM-DD).")]
DomainOpt = Annotated[str, typer.Option("--domain", help="Domain identifier.")]
ConfigDirOpt = Annotated[
    Path, typer.Option("--config-dir", help="Directory containing configuration contracts.")
]


def _not_implemented(command: str, milestone: str) -> NoReturn:
    typer.echo(
        f"codetalent {command}: not implemented yet — "
        f"Milestone {milestone} ({_MILESTONES[milestone]}) delivers this command."
    )
    raise typer.Exit(2)


@app.callback()
def main() -> None:
    """CodeTalent Atlas command-line interface."""


@app.command("version")
def version() -> None:
    """Print the installed CodeTalent Atlas version."""
    typer.echo(__version__)


def _format_bytes(num: int) -> str:
    for unit, factor in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if num >= factor:
            return f"{num / factor:.2f} {unit}"
    return f"{num} B"


def _parse_window(start: str, end: str) -> tuple[date, date]:
    try:
        return date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        typer.echo(f"[fail] invalid --start/--end date: {exc}")
        raise typer.Exit(2) from exc


def _load_config_or_exit(config_dir: Path) -> AtlasConfig:
    try:
        return load_all(config_dir)
    except ConfigError as exc:
        typer.echo(f"[fail] configuration invalid:\n{exc}")
        raise typer.Exit(1) from exc


def _pilot_domain(config: AtlasConfig) -> str:
    return next(
        domain_id
        for domain_id, entry in config.domains.domains.items()
        if entry.status.value == "pilot"
    )


def _build_plan_or_exit(
    config: AtlasConfig, settings: Settings, domain: str, window: tuple[date, date]
) -> list[bq_plan.QuerySpec]:
    try:
        return bq_plan.build_discovery_plan(
            config=config, settings=settings, domain_id=domain, start=window[0], end=window[1]
        )
    except (ConfigError, sqlgen.SqlRenderError) as exc:
        typer.echo(f"[fail] cannot build the discovery plan: {exc}")
        raise typer.Exit(1) from exc


def _build_client_or_exit(settings: Settings) -> bigquery.Client:
    try:
        return bq_runner.build_client(settings)
    except RuntimeError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc


@bq_app.command("dry-run")
def bq_dry_run(
    start: StartOpt = "2026-05-01",
    end: EndOpt = "2026-07-31",
    config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR,
) -> None:
    """Price the full discovery plan with free dry runs; execute nothing."""
    config = _load_config_or_exit(config_dir)
    settings = load_settings()
    window = _parse_window(start, end)
    domain = _pilot_domain(config)
    plan = _build_plan_or_exit(config, settings, domain, window)
    client = _build_client_or_exit(settings)
    runner = bq_runner.BigQueryRunner(client, settings, logger=RunLogger("phase3-dry-run"))

    months = bq_plan.months_in_window(*window)
    typer.echo("BigQuery discovery dry-run plan (nothing executes; dry runs are free)")
    typer.echo(
        f"  window: {start} → {end} (months: {', '.join(months)})  domain: {domain}\n"
        f"  project: {settings.google_cloud_project}  dataset: {settings.dataset_id}"
    )
    try:
        pricing = bq_plan.price_plan(
            plan,
            estimate_bytes=lambda spec: runner.estimate_query_bytes(spec.name, spec.sql),
            destination_has_rows=runner.destination_has_rows,
        )
    except (Unauthorized, Forbidden) as exc:
        typer.echo(f"[fail] BigQuery rejected the request: {exc}")
        typer.echo(bq_runner.CREDENTIALS_INSTRUCTIONS)
        raise typer.Exit(1) from exc

    cumulative = 0
    for estimate in pricing.estimates:
        if estimate.estimated_bytes is None:
            detail = estimate.note or "unpriced"
            typer.echo(f"  {estimate.name:<42} unpriced — {detail}")
            continue
        if estimate.will_skip:
            typer.echo(
                f"  {estimate.name:<42} {_format_bytes(estimate.estimated_bytes):>12}"
                "  (destination exists — will be skipped)"
            )
            continue
        cumulative += estimate.estimated_bytes
        typer.echo(
            f"  {estimate.name:<42} {_format_bytes(estimate.estimated_bytes):>12}"
            f"  cumulative {_format_bytes(cumulative)}"
        )

    budget = settings.bigquery_max_bytes_phase3
    consumed = runner.ledger.consumed_bytes(runner.phase)
    remaining_after = budget - consumed - pricing.planned_bytes
    priced = len(plan) - len(pricing.unpriced)
    typer.echo(
        f"Priced estimate for this run: {_format_bytes(pricing.planned_bytes)} "
        f"({priced} of {len(plan)} queries priced)"
    )
    if pricing.unpriced:
        typer.echo(
            f"  unpriced: {', '.join(pricing.unpriced)} — these read tables created earlier "
            "in the run; each is re-priced and byte-capped at execution time"
        )
    typer.echo(
        f"Phase 3 budget: {_format_bytes(budget)}; already consumed by executed queries: "
        f"{_format_bytes(consumed)}"
    )
    typer.echo(f"Remaining after this plan: {_format_bytes(remaining_after)}")
    if remaining_after >= 0:
        typer.echo("RESULT: PASS — plan fits within BIGQUERY_MAX_BYTES_PHASE3")
        return
    typer.echo("RESULT: FAIL — plan would exceed BIGQUERY_MAX_BYTES_PHASE3; do not execute")
    raise typer.Exit(1)


@bq_app.command("discover")
def bq_discover(
    domain: DomainOpt = "cloud_devops",
    start: StartOpt = "2026-05-01",
    end: EndOpt = "2026-07-31",
    config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR,
) -> None:
    """Run the guarded GH Archive discovery pipeline and export Parquet locally."""
    config = _load_config_or_exit(config_dir)
    settings = load_settings()
    window = _parse_window(start, end)
    plan = _build_plan_or_exit(config, settings, domain, window)
    client = _build_client_or_exit(settings)
    logger = RunLogger("phase3-discovery")
    runner = bq_runner.BigQueryRunner(client, settings, logger=logger)

    quality_rows: list[dict[str, object]] | None = None
    try:
        runner.ensure_dataset()
        for spec in plan:
            outcome = runner.execute(spec)
            if outcome.status == bq_runner.STATUS_SKIPPED:
                typer.echo(f"[skip] {spec.name}: destination already materialized")
            else:
                typer.echo(
                    f"[ok] {spec.name}: {_format_bytes(outcome.actual_bytes)} processed "
                    f"(estimated {_format_bytes(outcome.estimated_bytes)})"
                )
            if spec.fetch_rows:
                quality_rows = outcome.rows
    except bq_runner.BudgetExceededError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc
    except (Unauthorized, Forbidden) as exc:
        typer.echo(f"[fail] BigQuery rejected the request: {exc}")
        typer.echo(bq_runner.CREDENTIALS_INSTRUCTIONS)
        raise typer.Exit(1) from exc
    except NotFound as exc:
        typer.echo(f"[fail] BigQuery object not found: {exc}")
        raise typer.Exit(1) from exc

    failures = [row for row in quality_rows or [] if row.get("status") != "pass"]
    for row in quality_rows or []:
        marker = "ok" if row.get("status") == "pass" else "fail"
        typer.echo(
            f"[{marker}] quality check {row.get('check_name')}: "
            f"{row.get('failing_rows')} failing rows ({row.get('requirement')})"
        )
    if failures:
        typer.echo(f"[fail] {len(failures)} quality check(s) failed; not exporting.")
        raise typer.Exit(1)

    project = settings.google_cloud_project
    dataset = settings.dataset_id
    discovery_table = sqlgen.REPO_DISCOVERY_TABLE_FORMAT.format(domain_id=domain)
    contributor_table = sqlgen.CONTRIBUTOR_TABLE_FORMAT.format(domain_id=domain)
    export = bq_export.export_discovery_outputs(
        client,
        repo_discovery_table=f"{project}.{dataset}.{discovery_table}",
        contributor_table=f"{project}.{dataset}.{contributor_table}",
        domain_id=domain,
    )
    typer.echo(
        f"Funnel: {export.discovered_candidates} discovered candidates "
        "(spec 3.3 pilot target: 10,000+); "
        f"{export.activity_passed} activity-passed (target: 5,000+)."
    )
    typer.echo(f"Wrote {export.summary_path} ({export.summary_rows} rows)")
    typer.echo(f"Wrote {export.candidates_path} ({export.discovered_candidates} rows)")
    typer.echo(f"Wrote {export.contributor_path} ({export.contributor_rows} rows)")


@github_app.command("enrich-repos")
def github_enrich_repos(
    input_path: Annotated[
        Path, typer.Option("--input", help="Repository activity summary Parquet worklist.")
    ] = Path("data/interim/repository_activity_summary.parquet"),
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Attempt at most N pending repositories (smoke runs)."),
    ] = None,
    rate_limit_floor: Annotated[
        int,
        typer.Option(
            "--rate-limit-floor",
            min=1,
            help="Sleep until reset when remaining GraphQL points drop below this floor.",
        ),
    ] = 200,
    max_failure_retries: Annotated[
        int,
        typer.Option(
            "--max-failure-retries",
            min=1,
            help=(
                "Retry transient per-repository failures up to this many times; "
                "raise it to re-attempt repositories whose retry budget is exhausted."
            ),
        ),
    ] = 3,
    content_signals: Annotated[
        bool,
        typer.Option(
            "--content-signals/--no-content-signals",
            help=(
                "Also fetch README/CONTRIBUTING/CI/tests presence via git object "
                "lookups (slow; spec reserves this for the qualified shortlist)."
            ),
        ),
    ] = False,
) -> None:
    """Enrich accepted repositories through batched, cached, resumable GraphQL."""
    # Imported lazily so `codetalent --help` stays fast and dependency-light.
    from codetalent.github import enrich_repos as enrich_mod
    from codetalent.github.graphql_client import (
        TOKEN_SETUP_INSTRUCTIONS,
        GitHubAuthenticationError,
        SecondaryRateLimitError,
    )

    settings = load_settings()
    if settings.github_token is None:
        typer.echo("[fail] GITHUB_TOKEN is not set.")
        typer.echo(TOKEN_SETUP_INSTRUCTIONS)
        raise typer.Exit(1)

    try:
        report = enrich_mod.enrich_repositories(
            settings=settings,
            input_path=input_path,
            limit=limit,
            rate_limit_floor=rate_limit_floor,
            max_failure_retries=max_failure_retries,
            content_signals=content_signals,
            logger=RunLogger("phase4-enrich-repos"),
        )
    except enrich_mod.WorklistError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc
    except GitHubAuthenticationError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc
    except SecondaryRateLimitError as exc:
        typer.echo(f"[fail] {exc}")
        typer.echo("Progress is checkpointed; re-run the same command later to resume.")
        raise typer.Exit(1) from exc
    except enrich_mod.ErrorRateExceededError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc

    typer.echo(
        f"Worklist: {report.worklist_total} accepted repositories; "
        f"{report.already_completed} already completed (skipped)."
    )
    typer.echo(
        f"This run: {report.attempted} attempted, {report.succeeded} enriched, "
        f"{report.failed} failed (quarantined), {report.cache_hits} cache-hit batches."
    )
    typer.echo(f"Batch size: {report.batch_size} (persisted in checkpoint).")
    typer.echo(f"Wrote {report.output_path} ({report.total_rows} rows)")
    if report.exhausted_failures:
        shown = list(report.exhausted_failures.items())[:20]
        typer.echo(
            f"[warn] {len(report.exhausted_failures)} repositories exhausted their "
            f"retry budget ({max_failure_retries}) and are excluded from future runs:"
        )
        for name, reason in shown:
            typer.echo(f"  - {name}: {reason}")
        if len(report.exhausted_failures) > len(shown):
            typer.echo(f"  ... and {len(report.exhausted_failures) - len(shown)} more.")
        typer.echo("Re-run with a higher --max-failure-retries to retry them.")


@github_app.command("enrich-users")
def github_enrich_users(
    input_path: Annotated[
        Path, typer.Option("--input", help="Contributor activity Parquet worklist.")
    ] = Path("data/interim/contributor_activity.parquet"),
    qualified: Annotated[
        Path,
        typer.Option(
            "--qualified",
            help="Classification Parquet restricting the worklist to qualified repos.",
        ),
    ] = Path("data/interim/repository_classification.parquet"),
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Attempt at most N pending logins (smoke runs)."),
    ] = None,
    rate_limit_floor: Annotated[
        int,
        typer.Option(
            "--rate-limit-floor",
            min=1,
            help="Sleep until reset when remaining GraphQL points drop below this floor.",
        ),
    ] = 200,
) -> None:
    """Enrich public contributor profiles through batched, cached GraphQL.

    Fetches ONLY login, account type, public location, creation date, and
    followers count (spec 9.5). Output stays local and gitignored.
    """
    from codetalent.github import enrich_users as users_mod
    from codetalent.github.graphql_client import (
        TOKEN_SETUP_INSTRUCTIONS,
        GitHubAuthenticationError,
        SecondaryRateLimitError,
    )

    settings = load_settings()
    if settings.github_token is None:
        typer.echo("[fail] GITHUB_TOKEN is not set.")
        typer.echo(TOKEN_SETUP_INSTRUCTIONS)
        raise typer.Exit(1)

    if not qualified.is_file():
        typer.echo(
            f"[warn] {qualified} not found — enriching contributors of ALL "
            "activity-passed repositories (run `codetalent classify repos` first "
            "to restrict the worklist to qualified repositories)."
        )
    try:
        report = users_mod.enrich_users(
            settings=settings,
            activity_path=input_path,
            qualified_path=qualified if qualified.is_file() else None,
            limit=limit,
            rate_limit_floor=rate_limit_floor,
            logger=RunLogger("phase4-enrich-users"),
        )
    except users_mod.WorklistError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc
    except GitHubAuthenticationError as exc:
        typer.echo(f"[fail] {exc}")
        raise typer.Exit(1) from exc
    except SecondaryRateLimitError as exc:
        typer.echo(f"[fail] secondary rate limit: {exc} — checkpoint preserved; rerun later.")
        raise typer.Exit(1) from exc

    typer.echo(
        f"Worklist: {report.worklist_total} contributors; "
        f"{report.already_completed} already completed (skipped)."
    )
    typer.echo(
        f"This run: {report.attempted} attempted, {report.succeeded} enriched, "
        f"{report.failed} failed, {report.cache_hits} cache-hit batches."
    )
    typer.echo(f"Wrote {report.output_path} ({report.total_rows} rows; local only)")


@classify_app.command("repos")
def classify_repos(
    domain: DomainOpt = "cloud_devops",
    input_path: Annotated[
        Path, typer.Option("--input", help="Enriched repository metadata Parquet file.")
    ] = Path("data/interim/repository_metadata.parquet"),
    activity_path: Annotated[
        Path, typer.Option("--activity", help="Repository activity summary Parquet file.")
    ] = Path("data/interim/repository_activity_summary.parquet"),
    output_path: Annotated[
        Path, typer.Option("--output", help="Destination classification Parquet file.")
    ] = Path("data/interim/repository_classification.parquet"),
    config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR,
) -> None:
    """Classify enriched repositories against the domain taxonomy."""
    config = _load_config_or_exit(config_dir)
    if domain not in config.taxonomies:
        typer.echo(
            f"[fail] no taxonomy configured for domain {domain!r} "
            f"(available: {', '.join(sorted(config.taxonomies))})"
        )
        raise typer.Exit(1)

    # Imported lazily and dynamically: the classifier runner lands in its own
    # Milestone C work stream, and cli.py must import cleanly without it.
    try:
        runner_module = importlib.import_module("codetalent.classify.runner")
    except ModuleNotFoundError as exc:
        typer.echo(f"codetalent classify repos: classifier runner not available yet ({exc}).")
        raise typer.Exit(2) from exc

    result = runner_module.classify_repositories(
        config=config,
        domain_id=domain,
        metadata_path=input_path,
        activity_path=activity_path,
        output_path=output_path,
    )
    typer.echo(
        f"Classified {result.total} repositories: {result.accepted} accepted, "
        f"{result.rejected} rejected, {result.borderline} borderline."
    )
    typer.echo(f"Wrote {result.output_path}")


@locations_app.command("normalize")
def locations_normalize(
    profiles: Annotated[
        Path, typer.Option("--profiles", help="Enriched user profiles Parquet (local-only).")
    ] = Path("data/interim/user_profiles.parquet"),
    output: Annotated[
        Path, typer.Option("--output", help="Normalized locations Parquet (local-only).")
    ] = Path("data/interim/normalized_locations.parquet"),
    config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR,
) -> None:
    """Normalize public profile locations offline (no geocoding API, spec 15)."""
    config = _load_config_or_exit(config_dir)
    if not profiles.is_file():
        typer.echo(f"[fail] profiles parquet not found: {profiles} (run github enrich-users first)")
        raise typer.Exit(1)
    # Imported lazily: the gazetteer stack is heavy and irrelevant to --help.
    from codetalent.locations.runner import normalize_profile_locations

    summary = normalize_profile_locations(config, profiles, output)
    typer.echo(
        f"Normalized {summary.total} profiles: {summary.located_country} with a country "
        f"({summary.coverage_country_rate:.1%} coverage), {summary.located_city} with a city, "
        f"{summary.unusable} unusable."
    )
    typer.echo(f"Wrote {summary.output_path} (local only; never published)")


@score_app.command("repositories")
def score_repositories() -> None:
    """Compute repository quality scores."""
    _not_implemented("score repositories", "E")


@score_app.command("contributors")
def score_contributors() -> None:
    """Compute contributor expert scores."""
    _not_implemented("score contributors", "E")


@score_app.command("geographies")
def score_geographies() -> None:
    """Compute country/city opportunity, confidence, and tiers."""
    _not_implemented("score geographies", "E")


@publish_app.command("web-data")
def publish_web_data() -> None:
    """Build the aggregate-only static datasets for the web app."""
    _not_implemented("publish web-data", "F")


def _run_config_validation(config_dir: Path) -> AtlasConfig:
    """Load every configuration contract, echoing a short summary. Raises ConfigError."""
    config = load_all(config_dir)
    subdomain_count = sum(len(t.subdomains) for t in config.taxonomies.values())
    typer.echo(
        f"[ok] configuration valid: {len(config.domains.domains)} domains, "
        f"{len(config.taxonomies)} taxonomies ({subdomain_count} subdomains), "
        f"{len(config.location_aliases)} location aliases, "
        f"{len(config.location_overrides)} location overrides."
    )
    return config


def _run_privacy_scan() -> int:
    """Scan public data directories; echo results and return the violation count."""
    violations = scan_public_data()
    if violations:
        typer.echo(f"[fail] privacy scan: {len(violations)} violation(s) in public data:")
        for violation in violations:
            typer.echo(f"  - {violation.file}: {violation.pattern}: {violation.excerpt}")
    else:
        scanned = ", ".join(str(d) for d in DEFAULT_PUBLIC_DIRS)
        typer.echo(f"[ok] privacy scan: no prohibited content under {scanned}.")
    return len(violations)


@validate_app.command("all")
def validate_all(config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR) -> None:
    """Run all available validation stages; report later-milestone stages as pending."""
    try:
        _run_config_validation(config_dir)
    except ConfigError as exc:
        typer.echo(f"[fail] configuration invalid:\n{exc}")
        raise typer.Exit(1) from exc

    violation_count = _run_privacy_scan()

    typer.echo("[pending] data quality checks — Milestone E (scoring and validation).")
    typer.echo("[pending] classification validation — Milestone C, sampling in Milestone E.")
    typer.echo("[pending] location validation — Milestone D, precision gates in Milestone E.")
    typer.echo("[pending] ranking stability and bias analysis — Milestone E.")

    if violation_count:
        raise typer.Exit(1)
    typer.echo("validate all: all available stages passed.")


_PILOT_STAGES: tuple[tuple[str, str], ...] = (
    ("config-validation", "validate configuration contracts (available now)"),
    ("bq-discover", "GH Archive discovery via BigQuery — live execution, needs GCP credentials"),
    ("github-enrich-repos", "repository enrichment — Milestone C, needs GITHUB_TOKEN"),
    ("classify-repos", "taxonomy classification — Milestone C"),
    ("github-enrich-users", "user profile enrichment — Milestone D, needs GITHUB_TOKEN"),
    ("locations-normalize", "offline location normalization — Milestone D"),
    ("score-repositories", "repository quality scoring — Milestone E"),
    ("score-contributors", "contributor expert scoring — Milestone E"),
    ("score-geographies", "opportunity and confidence ranking — Milestone E"),
    ("validate-all", "full validation suite — Milestone E"),
    ("publish-web-data", "aggregate-only web data build — Milestone F"),
)


@pipeline_app.command("pilot")
def pipeline_pilot(config_dir: ConfigDirOpt = DEFAULT_CONFIG_DIR) -> None:
    """Run all safe local pilot stages in order; stop at the first unavailable stage."""
    typer.echo("Pilot pipeline stages:")
    for index, (name, description) in enumerate(_PILOT_STAGES, start=1):
        typer.echo(f"  {index}. {name}: {description}")
    typer.echo("")

    logger = RunLogger("pipeline-pilot")
    with logger.timed("config-validation"):
        try:
            _run_config_validation(config_dir)
        except ConfigError as exc:
            typer.echo(f"[fail] configuration invalid:\n{exc}")
            raise typer.Exit(1) from exc

    typer.echo(
        "pipeline pilot stopped before stage 'bq-discover': it executes live BigQuery "
        "queries and requires Google Cloud credentials. Run it explicitly with "
        "`codetalent bq dry-run` (free cost preview) and then "
        "`codetalent bq discover --domain cloud_devops`. Completed 1 of "
        f"{len(_PILOT_STAGES)} stages."
    )
    raise typer.Exit(2)


if __name__ == "__main__":
    app()
