"""Typer CLI wired to the spec section 24 command surface.

Commands that belong to later milestones print a one-line message naming the
milestone that implements them and exit with code 2. ``validate all`` and
``pipeline pilot`` already run the real local stages that exist today
(configuration validation and the public-data privacy scan).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, NoReturn

import typer

from codetalent import __version__
from codetalent.config import DEFAULT_CONFIG_DIR, AtlasConfig, ConfigError, load_all
from codetalent.runlog import RunLogger
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


@bq_app.command("dry-run")
def bq_dry_run(start: StartOpt = "2026-05-01", end: EndOpt = "2026-07-31") -> None:
    """Estimate BigQuery bytes for the discovery window without executing."""
    _not_implemented("bq dry-run", "B")


@bq_app.command("discover")
def bq_discover(
    domain: DomainOpt = "cloud_devops",
    start: StartOpt = "2026-05-01",
    end: EndOpt = "2026-07-31",
) -> None:
    """Run guarded GH Archive discovery queries and export candidates locally."""
    _not_implemented("bq discover", "B")


@github_app.command("enrich-repos")
def github_enrich_repos(
    input_path: Annotated[
        Path, typer.Option("--input", help="Candidate repositories Parquet file.")
    ] = Path("data/interim/candidates.parquet"),
) -> None:
    """Enrich candidate repositories through batched GraphQL."""
    _not_implemented("github enrich-repos", "C")


@github_app.command("enrich-users")
def github_enrich_users(
    input_path: Annotated[
        Path, typer.Option("--input", help="Contributor logins Parquet file.")
    ] = Path("data/interim/contributors.parquet"),
) -> None:
    """Enrich public contributor profiles through batched GraphQL."""
    _not_implemented("github enrich-users", "D")


@classify_app.command("repos")
def classify_repos(domain: DomainOpt = "cloud_devops") -> None:
    """Classify enriched repositories against the domain taxonomy."""
    _not_implemented("classify repos", "C")


@locations_app.command("normalize")
def locations_normalize() -> None:
    """Normalize public profile locations offline."""
    _not_implemented("locations normalize", "D")


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
    ("bq-discover", "GH Archive discovery via BigQuery — Milestone B, needs GCP credentials"),
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
        "pipeline pilot stopped before stage 'bq-discover': it requires Google Cloud "
        "credentials and Milestone B (BigQuery discovery), which is not implemented yet. "
        "Completed 1 of "
        f"{len(_PILOT_STAGES)} stages."
    )
    raise typer.Exit(2)


if __name__ == "__main__":
    app()
