# data/

Local data workspace for the CodeTalent Atlas pipeline. Layout and commit rules come from build-spec sections 7, 14, and 15.

## Layout

| Directory | Contents | Committed? |
|---|---|---|
| `raw/` | Unmodified exports from BigQuery discovery runs (sandbox tables expire, so results are persisted here) | **No — gitignored** |
| `cache/` | Cached external responses keyed by normalized request hash: `cache/github/graphql/repositories/`, `cache/github/graphql/users/`, `cache/github/rest/` | **No — gitignored** |
| `interim/` | Intermediate pipeline artifacts: activity summaries, candidate tables, enrichment checkpoints (`interim/checkpoints/`) | **No — gitignored** (user-level and bulky) |
| `processed/` | Scored, user-level datasets (contributor scores, normalized locations) | **No — gitignored** (contains individual-level records) |
| `samples/` | Small, curated samples used by tests and manual validation | **Yes** — small files only |
| `public/` | Aggregate-only outputs destined for publication; must pass the privacy scanner | **Yes** — aggregates only |

## Why raw, cache, and user-level files are gitignored

1. **Privacy.** Everything individual-level — `actor_login`, raw location strings, profile enrichment, `actor_login -> location` mappings — stays local. Only aggregates are ever committed or published (see `docs/privacy_ethics.md`).
2. **Reproducibility without bulk.** Every external response is cached so runs are deterministic and resumable, but caches are machine-local state, not source. The lineage log (`docs/data_lineage.md`) records the exact commands that regenerate every artifact.
3. **Size.** Raw event exports and caches are far too large for a source repository.

## Commit rule

Only two kinds of data are ever committed:

- **Small samples** in `samples/` — fixtures and stratified validation sets, kept small deliberately.
- **Aggregate public assets** in `public/` — location-level scores, counts, and summaries that have passed the privacy scanner (no `actor_login`, no `user_login`, no profile URLs, no raw location strings, no emails, no names, no tokens).

If a file does not fit one of those two categories, it does not get committed. The privacy scanner blocks the build and deployment on any violation in `public/`.

## Population schedule

All directories are empty at Milestone A (placeholders only). They are populated by later milestones: `raw/` and `interim/` by Milestone B (BigQuery discovery), `cache/` by Milestones C–D (GitHub enrichment), `processed/` by Milestones D–E (locations and scoring), `samples/` by Milestones B–E as validation sets are drawn, and `public/` by Milestone F (static web data build).
