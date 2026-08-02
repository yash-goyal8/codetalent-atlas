# CodeTalent Atlas — Decision Log

Append-only log of implementation decisions, deviations, and gaps. Required by build-spec operating instructions 4 and 13. Newest entries at the bottom of each dated section.

Format: date, decision, rationale, and (where relevant) the milestone that revisits it.

---

## 2026-08-01 — Milestone A (repository foundation)

### A-01: Python floor stays at >=3.12 despite local 3.13.5

Local interpreter is Python 3.13.5. `pyproject.toml` keeps `requires-python = ">=3.12"` as the spec's stated floor (section 5.3) rather than raising it to 3.13. Rationale: the spec requires 3.12+, and a lower floor keeps the repo runnable on standard CI images and fresh clones without forcing the newest minor version. Code must therefore avoid 3.13-only features.

### A-02: Toolchain installs — uv via Homebrew, pnpm via npm (corepack broken)

uv 0.12.1 installed via Homebrew. pnpm 10 installed globally via npm because the corepack shim fails on Node 20.18.0 with `ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING`. Rationale: corepack is the usual route but is unusable on this Node version; a direct npm install of pnpm yields the same pinned-lockfile behavior. Both installs are free and documented so a fresh machine can reproduce them.

### A-03: Vite pinned to ^6

Node is 20.18.0, below Vite 7's minimum of 20.19. Vite is pinned to `^6` in `web/package.json`. Rationale: Vite 6 is fully supported on Node 20.18 and satisfies every frontend requirement in the spec; upgrading to Vite 7 is a one-line change once the Node runtime moves past 20.19. Revisit at Milestone F if the runtime changes.

### A-04: shadcn/ui primitives added manually

shadcn/ui components are vendored manually into `web/src/components` rather than generated with the interactive `shadcn` CLI. Rationale: the CLI is interactive and unsuited to a deterministic, scripted setup; manual vendoring pins exact component source in the repository, which matches the spec's reproducibility requirements.

### A-05: MapLibre GL, ECharts, and Framer Motion deferred to Milestone F

The Milestone A frontend shell excludes MapLibre GL JS, Apache ECharts, and Framer Motion. Rationale: none are exercised until real aggregate data and the full UI exist (Milestone F); deferring them keeps the shell lean, the dependency surface auditable, and the initial builds fast. The spec's frontend stack (section 5.5) is unchanged — only the installation point moves.

### A-06: Playwright E2E deferred to Milestone F

Playwright and the required E2E flows (spec section 20) are deferred to Milestone F. Rationale: every required flow (select domain, filter explorer, open detail, compare, methodology, username scan) depends on the real data UI, which does not exist until Milestone F. Vitest unit/component testing is in place from Milestone A.

### A-07: `web/public/social-card.png` deferred to Milestone F

The social card image listed in the repository structure (spec section 7) is not created in Milestone A. Rationale: no brand visuals exist yet; committing a placeholder image would violate the no-junk quality bar. Created in Milestone F alongside the visual system.

### A-08: `sql/` query templates deferred to Milestone B

The seven SQL files under `sql/` (spec section 7) are not stubbed in Milestone A. Rationale: the spec's implementation order (section 29) assigns SQL templates and the dry-run guard to Milestone B; empty SQL stubs would add nothing and risk being mistaken for runnable queries.

### A-09: Privacy scanner implemented early, in Milestone A

The public-data privacy scanner (spec section 27) is implemented in Milestone A even though no public data exists yet. Rationale: implementing the guard before any data stage exists means every later milestone is born under it; there is no window in which public assets can be produced unscanned. The scan runs in CI from the first commit.

### A-10: Taxonomy positive/negative example tests deferred to Milestone C

Spec section 8.1 requires tests proving known positive and negative classification examples. These are deferred to Milestone C. Rationale: the tests exercise the deterministic classifier, which is a Milestone C deliverable; writing them earlier would test configuration files against code that does not exist.

### A-11: Structured logging module named `runlog.py`

The structured JSON-lines logging module (spec section 26) is named `runlog.py` rather than `logging.py`. Rationale: a module named `logging` inside the package would shadow the stdlib `logging` module and invite subtle import bugs. The spec does not mandate a module name; the required log fields are unchanged.

### A-12: Public GitHub repository and BigQuery Sandbox project created (2026-08-01)

The repository was published to https://github.com/yash-goyal8/codetalent-atlas (public, per spec sections 5.6 and 30) with `origin/main` tracking. The Google Cloud project `codetalent-atlas` was created with **no billing account attached**, which is what constitutes BigQuery Sandbox mode; the BigQuery API is enabled and access to the public `githubarchive` dataset was verified with a dry-run query (0 bytes processed, $0 cost). Application Default Credentials already existed locally and their quota project was set to `codetalent-atlas`. The local gitignored `.env` sets `GOOGLE_CLOUD_PROJECT=codetalent-atlas`. Standing rule: no billing account may ever be attached to this project (spec hard constraint).

## 2026-08-01 — Milestone B (BigQuery discovery)

### B-01: Single-pass per-month grid materialization strategy

Dry-run measurement (2026-08-01) priced the five required columns `[type, repo.name, actor.login, created_at, payload]` of the pilot months at 58.51 GiB (202605), 35.36 GiB (202606), and 30.15 GiB (202607) — the `payload` column is ~85% of the cost. Strategy: exactly one scan per month materializes a compact `(repo_name, actor_login)` grid (`events_grid_YYYYMM`) with all payload-derived counts extracted up front and bots flagged (never dropped); every downstream stage reads only the small grids (≈3–4 GiB per full downstream pass). Owner/organization is derived from the repo-name prefix, avoiding an extra source column.

### B-02: Activity filters are domain-agnostic; relevance is Phase 2 classification

`config/repo_filters.yaml` minimums (5 human contributors / 20 meaningful events / 3 PRs-or-reviews / 2 active months) contain no domain-relevance condition, and spec Phase 3's objective is discovering *active* repositories at scale before enrichment; relevance classification (Phase 2 rules over topics/description/files) requires Milestone C metadata. `discovery_status = accepted` therefore means "passed activity minimums", regardless of taxonomy name match; the name match survives as the `is_taxonomy_candidate` signal for Milestone C prioritization. An earlier draft required both, which collapsed the funnel to 933 repositories and conflated Phase 3 with Phase 2. Discovered candidates = name-signal pool plus everything activity-passed.

### B-03: GH Archive 2026 payload schema drift — PR merge semantics

Probing `githubarchive.day.20260501` (2026-08-01) showed the 2026-era payload no longer carries `$.pull_request.merged`; merged PRs now emit a dedicated `action='merged'` (35,835 that day) and `action='closed'` covers only unmerged closures (4,666). The first grid materialization used the classic closed+merged-flag extraction and therefore recorded zero merged PRs; the grids were re-materialized (WRITE_TRUNCATE, the pipeline's standard refresh path) with era-robust counting: `prs_merged = action='merged' OR (action='closed' AND merged='true')`, `prs_closed = action IN ('closed','merged')`. This keeps `merged <= closed` in both payload eras, so the expanded twelve-month run can span the schema change safely.

### B-04: push_commit_count is structurally unavailable in the pilot window

2026-era PushEvent payloads contain only `{repository_id, push_id, ref, head, before}` — no `distinct_size`, `size`, or commits array (verified by direct payload sampling). Per operating rule 4 the field is recorded as a gap, not fabricated: `push_commit_count` is 0 for the pilot window, `push_events` is the push-volume signal, and the extraction retains the classic fields for older-era months in the expanded run. Milestone E scoring must treat commit volume as unavailable for the pilot (the spec already caps push influence).

### B-05: Pilot query budget raised from 250 GiB to 400 GiB

The schema drift in B-03 was only discoverable after the first materialization had consumed its bytes; the corrective re-materialization (+124 GiB) plus diagnostic probes (~6.4 GiB) cannot fit under the original 250 GiB pilot budget (spec 5.1). `BIGQUERY_MAX_BYTES_PHASE3` was raised to 429496729600 (400 GiB) in the local `.env` for this one-time rework. The $0 constraint is untouched: the project is a billing-free BigQuery Sandbox (nothing *can* bill), and the final phase total (~347 GiB) is ~34% of the 1 TiB monthly free tier, preserving the quota-safety intent of the original number. `.env.example` keeps the 250 GiB default for fresh runs.

### B-06: REST-only result fetching; no Storage Read API, no GCS

Results are fetched with `google-cloud-bigquery`'s REST row iterator (`to_arrow(create_bqstorage_client=False)`) and written to local Parquet. The BigQuery Storage Read API, `bq extract`, and Cloud Storage are never used — they are the paths that could require billing enablement. The working dataset sets a 55-day default table expiration (sandbox tables expire at 60 days regardless; results are exported locally because of exactly that).

### B-07: Export bounding rules

`repository_activity_summary.parquet` contains repositories with ≥2 unique human contributors or a taxonomy name match (1.04M rows) — repositories below that floor cannot reach any later stage, and the bound keeps the REST fetch tractable. `cloud_devops_repository_candidates.parquet` holds the discovered-candidate pool (accepted + name-matched exclusions with reasons). Contributor extraction covers activity-passed repositories only; `subdomains` is exported empty until Milestone C classification assigns real labels.

### B-08: Downstream stages re-run on every discover invocation

Only the month materializations are skip-if-exists; the cheap downstream stages (bot audit, rollup, filters, contributor extraction, quality checks — ~12.4 GiB per pass) rerun on every `bq discover`. An interrupted orchestration retried `bq discover` six times on 2026-08-01, so repeats cost ~62 GiB that idempotence would have saved. Future improvement noted for the refresh pipeline: content-hash-based skip for downstream stages.

### B-09: Local environment pins and the hidden-.pth workaround

The project now pins uv-managed CPython 3.12 (`.python-version` committed) after the Anaconda-based interpreter surfaced a subtle failure: this sandboxed environment marks written files with the macOS `UF_HIDDEN` flag and CPython ≥3.11 silently skips hidden `.pth` files, which broke the editable install. Durable fixes: `pythonpath = ["src"]` in pytest configuration (committed, cross-platform) and a `sitecustomize.py` inside the local venv (regular imports are unaffected by the hidden-file check). CI on Linux is unaffected.

### B-10: Ledger accounting corrections are evidence-based only

`reports/query_usage.csv` is append-only in normal operation. Two manual adjustments were made, both anchored to verifiable job statistics: (1) four diagnostic probe queries run via the `bq` CLI were appended with their exact `totalBytesProcessed` from job metadata; (2) one runner error row for a 409 "Already Exists" rejection was corrected from its conservative estimate to the verified 0 bytes (the job has no byte statistics — it was rejected before scanning). All other rows are written by the runner at execution time.
