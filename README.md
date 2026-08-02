# CodeTalent Atlas

A public-data sourcing-intelligence product that ranks countries and cities by observable expert developer activity — built, processed, hosted, and refreshed for exactly $0.

## The question

> Where should Scale investigate and build sourcing pipelines for expert contributors across high-value coding domains?

CodeTalent Atlas answers a narrower, defensible version of that question: among observable, active contributors to qualified public repositories, which locations show the strongest combination of expert supply, quality, collaboration depth, momentum, and ecosystem breadth for a selected coding domain?

- **Pilot domain:** Cloud and DevOps (8 subdomains, from Infrastructure as Code to SRE)
- **Pilot window:** 2026-05-01 through 2026-07-31
- **Hard constraint:** $0 total cost — no paid API, database, model, hosting feature, or billing-enabled service anywhere in the pipeline

## Architecture

Free public data in, static aggregate-only site out:

```text
GH Archive monthly tables
        |
        v
BigQuery discovery SQL          (BigQuery Sandbox, no billing, bytes-capped)
        |
        v
Candidate repository activity table
        |
        v
GitHub GraphQL repository enrichment
        |
        v
Qualified repository table
        |
        v
GH Archive contributor-domain activity
        |
        v
GitHub GraphQL user profile enrichment
        |
        v
Offline location normalization  (pycountry / geonamescache / curated aliases — no geocoding API)
        |
        v
Repository and contributor scoring
        |
        v
Country/city opportunity + confidence scores
        |
        v
Validation and bias checks
        |
        v
Static web datasets             (aggregate-only JSON, privacy-scanned)
        |
        v
React analytical dashboard on Cloudflare Pages
```

Every score is transparent and reproducible; opportunity and data confidence are always reported separately.

## Quickstart

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20.18+, pnpm 10.

```bash
uv sync --all-groups   # Python dependencies from uv.lock
pnpm install           # frontend dependencies from pnpm-lock.yaml
make qa                # lint + typecheck + test + build, both stacks
```

Individual gates, if you prefer them raw:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run mypy src
pnpm --dir web lint && pnpm --dir web typecheck && pnpm --dir web test && pnpm --dir web build
```

Copy `.env.example` to `.env` for local credential configuration. No credentials are needed for Milestone A — nothing in the current codebase calls an external service.

## CLI

The `codetalent` Typer CLI is the single entry point for the pipeline:

```bash
codetalent bq dry-run --start 2026-05-01 --end 2026-07-31
codetalent bq discover --domain cloud_devops --start 2026-05-01 --end 2026-07-31
codetalent github enrich-repos --input data/interim/candidates.parquet
codetalent classify repos --domain cloud_devops
codetalent github enrich-users --input data/interim/contributors.parquet
codetalent locations normalize
codetalent score repositories
codetalent score contributors
codetalent score geographies
codetalent validate all
codetalent publish web-data
codetalent pipeline pilot
```

Milestone A ships the command skeleton: every command is registered and validated, and each pipeline stage that is not yet implemented exits with a clear message naming the milestone that delivers it.

## Repository layout

```text
config/     Domain taxonomy, filters, scoring weights, bot patterns, location aliases
sql/        BigQuery discovery SQL (dry-run guarded, bytes-capped)
src/        Python package: codetalent (CLI, schemas, settings, pipeline modules)
scripts/    Stage entry-point scripts
tests/      pytest suites: unit, integration, fixtures, snapshots
data/       raw/cache/interim/processed are gitignored; samples/ and public/ are committed
reports/    Query usage, validation, and data-dictionary reports
web/        Vite + React + TypeScript dashboard (pnpm workspace member)
docs/       Build spec, product spec, methodology, decisions, privacy and bias docs
.github/    CI, manual data-refresh, and deployment-documentation workflows
```

## Project status

**Milestone B complete — BigQuery discovery.** The Cloud/DevOps pilot discovery ran end-to-end over GH Archive (2026-05-01 → 2026-07-31): 309,653 candidate repositories discovered, 19,456 passing activity filters, 204,202 unique human contributors observed — at $0, using 33.9% of the BigQuery Sandbox free tier. Evidence: [`reports/discovery_validation.md`](reports/discovery_validation.md). Next: **Milestone C, GitHub enrichment and classification** — batched GraphQL repository metadata, deterministic taxonomy classifier, manual validation gate.

## Methodology and limitations

The authoritative specification, including every scoring formula, threshold, validation gate, and known bias, lives in [`docs/CODETALENT_ATLAS_BUILD_SPEC.md`](docs/CODETALENT_ATLAS_BUILD_SPEC.md); the product definition is in [`docs/product_spec.md`](docs/product_spec.md). Methodology, decision-log, and bias-limitation documents accumulate in `docs/` as milestones land. This product measures observable public GitHub activity — it does not claim to measure the total developer workforce.

## Privacy stance

Public output is **aggregate-only**. The site and the committed public datasets never contain usernames, raw location strings, emails, or any individual developer ranking. A privacy scanner (`make privacy-scan`) enforces this, and CI blocks deployment on any violation.

## License

MIT — see [LICENSE](LICENSE).
