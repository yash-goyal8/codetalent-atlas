# CodeTalent Atlas — Data Lineage Log

Required by build-spec operating instruction 13. Every dataset the pipeline produces gets a row here: what produced it, from which inputs, with which command, and when. A dataset with no row does not exist; a row marked **not yet run** is a planned stage, not a produced artifact.

Rules:

- Update this table in the same change that produces or regenerates a dataset.
- Commands must be the exact documented CLI invocations, so every artifact is reproducible from a fresh clone.
- Dates are the run dates, in UTC.

---

## Lineage table

| Dataset | Produced by | Inputs | Command | Date | Notes |
|---|---|---|---|---|---|
| `data/interim/repository_activity_summary.parquet` | BigQuery discovery (Milestone B) | GH Archive months 202605-202607, `config/repo_filters.yaml`, `config/bot_patterns.yaml`, `config/scoring.yaml` | `codetalent bq discover --domain cloud_devops --start 2026-05-01 --end 2026-07-31` | 2026-08-02 | 1,052,819 rows; grids re-materialized for 2026 payload era (decisions B-03/B-05); ledger in `reports/query_usage.csv` |
| `data/interim/cloud_devops_repository_candidates.parquet` | BigQuery discovery (Milestone B) | `repository_activity_summary.parquet`, activity filters, taxonomy name signal | `codetalent bq discover --domain cloud_devops --start 2026-05-01 --end 2026-07-31` | 2026-08-02 | 309,653 discovered; 19,456 activity-passed (decision B-02) |
| Repository metadata (enriched) | GitHub GraphQL repository enrichment (Milestone C) | `cloud_devops_repository_candidates.parquet`, GraphQL cache | `codetalent github enrich-repos --input data/interim/candidates.parquet` | — | **not yet run** |
| Repository classification (qualified repositories) | Deterministic taxonomy classifier (Milestone C) | Enriched repository metadata, `config/cloud_devops_taxonomy.yaml` | `codetalent classify repos --domain cloud_devops` | — | **not yet run** |
| `data/interim/contributor_activity.parquet` | GH Archive contributor extraction (Milestone B; subdomain labels assigned in Milestone C) | Activity-passed repositories, event grids | `codetalent bq discover` contributor stage (`sql/05_extract_contributor_activity.sql`) | 2026-08-02 | 276,938 rows, 204,202 unique human contributors; local and gitignored |
| Public user profile enrichment | GitHub GraphQL user enrichment (Milestone D) | Contributor activity, GraphQL cache | `codetalent github enrich-users --input data/interim/contributors.parquet` | — | **not yet run**; local and gitignored, never published |
| Normalized locations | Offline location normalization (Milestone D) | User profile enrichment, `config/location_aliases.csv`, `config/location_overrides.csv`, offline gazetteers | `codetalent locations normalize` | — | **not yet run**; local and gitignored, never published |
| Repository quality scores | Scoring (Milestone E) | Qualified repositories, activity summaries, `config/scoring.yaml` | `codetalent score repositories` | — | **not yet run** |
| Contributor expert scores | Scoring (Milestone E) | Contributor activity, repository scores, normalized locations, `config/scoring.yaml` | `codetalent score contributors` | — | **not yet run** |
| Country/city opportunity and confidence rankings | Geographic scoring (Milestone E) | Contributor scores, normalized locations, `config/scoring.yaml` | `codetalent score geographies` | — | **not yet run** |
| Validation and bias reports | Validation suite (Milestone E) | All scored datasets, manual validation samples | `codetalent validate all` | — | **not yet run** |
| `data/public/` and `web/public/data/` aggregate assets | Static web data builder (Milestone F) | Rankings, validation outputs; privacy scanner must pass | `codetalent publish web-data` | — | **not yet run**; aggregate-only, scanner-gated |
