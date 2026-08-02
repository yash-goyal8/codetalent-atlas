# AGENTS.md — Operating Guide for Coding Agents

## Source of truth

`docs/CODETALENT_ATLAS_BUILD_SPEC.md` is the authoritative build specification. Read the relevant sections before changing anything. Do not silently change any formula, threshold, field, or requirement it defines.

## Operating rules (spec section 1, condensed)

1. Implement phases in numerical order.
2. Do not skip acceptance tests.
3. Do not silently change a scoring formula, threshold, data field, or UI requirement.
4. If a source field is unavailable, record the gap in `docs/decisions.md`; never fabricate it.
5. Every data-processing step must be deterministic and rerunnable.
6. Cache every external response locally.
7. Never commit secrets, tokens, raw emails, or private data.
8. The public website exposes only aggregates — never rank or display individual developers.
9. Prefer static precomputed files over a runtime backend.
10. Never add a service that can create a charge, even with a free trial. Total cost stays $0.
11. Use conservative API concurrency and obey all rate-limit headers.
12. After each phase, run its test suite and produce its required report before moving on.
13. Keep the decision log at `docs/decisions.md` and the data lineage log at `docs/data_lineage.md`.
14. Pin dependencies via lockfiles (`uv.lock`, `pnpm-lock.yaml`).
15. The repository must work from a fresh clone using documented commands.

## Build and test commands

Python (managed by uv; requires Python 3.12+):

```bash
uv sync --all-groups        # install all dependency groups from uv.lock
uv run ruff check .         # lint
uv run ruff format --check .# format check
uv run pytest               # tests
uv run mypy src             # static types
```

Frontend (pnpm workspace at the repo root; web app in `web/`):

```bash
pnpm install                # install from pnpm-lock.yaml, run at repo root
pnpm --dir web dev          # dev server
pnpm --dir web lint
pnpm --dir web typecheck
pnpm --dir web test
pnpm --dir web build
```

Privacy scan (scanner tests are named with "privacy"):

```bash
uv run pytest -k privacy
```

Make targets wrap the same commands: `make setup`, `make lint`, `make format`, `make typecheck`, `make test`, `make build`, `make qa` (lint + typecheck + test + build), `make privacy-scan`, `make clean`.

## File layout

```text
config/           YAML/CSV configuration contracts (taxonomy, filters, scoring, bots, aliases)
sql/              BigQuery SQL, numbered by pipeline stage
src/codetalent/   Python package: cli.py, settings.py, schemas.py, plus
                  bigquery/, github/, classify/, locations/, scoring/, validation/, publish/
scripts/          Stage entry-point scripts
tests/            unit/, integration/, fixtures/, snapshots/
data/             raw/, cache/, interim/, processed/ gitignored (keep .gitkeep);
                  samples/ and public/ committed
reports/          Usage and validation reports
web/              Vite + React + TypeScript app (src/, public/data/, public/geo/)
docs/             Spec, product docs, methodology, decisions, privacy, bias
.github/workflows ci.yml, refresh-data.yml, deploy.yml
```

## Privacy red lines

- No usernames (`actor_login`, `user_login`), GitHub profile URLs, raw location strings, emails, names, or tokens in `data/public/` or `web/public/data/` — ever.
- Public output is aggregate-only: counts, scores, country/city names, repository and organization counts, subdomain summaries.
- The privacy scanner (`uv run pytest -k privacy`) blocks builds and deployments on any violation. Do not weaken it to make a build pass.
- User-level files stay in gitignored `data/` directories and never leave the machine.

## Milestone status

**Milestone A is complete** — repository foundation: monorepo structure, Python and frontend tooling, Pydantic schemas, configuration loading, structured logging, Typer CLI skeleton, test setup, and CI. Pipeline stages are stubs that exit with a message naming the milestone that implements them.

**Milestone B complete** — BigQuery discovery ran end-to-end (see `reports/discovery_validation.md` and decisions B-01..B-10; note the 2026 GH Archive payload schema drift in B-03/B-04). **Milestone C is next** — GitHub GraphQL repository enrichment (batched, cached, checkpointed, rate-limit-aware), the deterministic taxonomy classifier, and the 150-repository manual validation gate (>=90% precision).
