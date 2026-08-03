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
| `data/interim/repository_metadata.parquet` | GitHub GraphQL repository enrichment (Milestone C) | Activity-passed worklist, GraphQL cache/checkpoints | `codetalent github enrich-repos` (+ qualified content pass) | 2026-08-03 | 19,223 rows (98.8%); content signals on qualified shortlist |
| `data/interim/repository_classification.parquet` | Deterministic taxonomy classifier (Milestone C) | Enriched metadata + activity summary, `config/cloud_devops_taxonomy.yaml`, `config/scoring.yaml` classification block | `codetalent classify repos --domain cloud_devops` | 2026-08-03 | 639 accepted / 790 borderline / 17,794 rejected; 92% precision gate passed |
| `data/interim/contributor_activity.parquet` | GH Archive contributor extraction (Milestone B; subdomain labels assigned in Milestone C) | Activity-passed repositories, event grids | `codetalent bq discover` contributor stage (`sql/05_extract_contributor_activity.sql`) | 2026-08-02 | 276,938 rows, 204,202 unique human contributors; local and gitignored |
| `data/interim/user_profiles.parquet` | GitHub GraphQL user enrichment (Milestone D) | Contributor activity restricted to qualified repos, GraphQL cache/checkpoints | `codetalent github enrich-users` | 2026-08-03 | 10,500 profiles (99.2% success); local and gitignored, never published |
| `data/interim/normalized_locations.parquet` | Offline location normalization (Milestone D) | `user_profiles.parquet`, alias/override CSVs, offline gazetteers | `codetalent locations normalize` | 2026-08-03 | 46.6% country coverage; 100%/100% precision gates; local and gitignored |
| `data/interim/repository_scores.parquet` | Scoring (Milestone E) | Activity + metadata + classification, `config/scoring.yaml` | `codetalent score repositories` | 2026-08-03 | 639 rows, median 49.6 |
| `data/interim/contributor_scores.parquet` | Scoring (Milestone E) | Contributor activity, repository scores, normalized locations, `config/scoring.yaml` | `codetalent score contributors` | 2026-08-03 | 5,636 rows, median 39.5; local and gitignored |
| `data/interim/geographic_rankings.parquet` | Geographic scoring (Milestone E) | Contributor scores + activity + classification + locations, `config/scoring.yaml` | `codetalent score geographies` | 2026-08-03 | 343 rows (23 countries + 5 cities rankable); sensitivity-tested |
| Validation and bias reports | Validation suite (Milestone E) | All scored datasets, manual validation samples | `codetalent validate all` | — | **not yet run** |
| `data/public/` and `web/public/data/` aggregate assets | Static web data builder (Milestone F) | All scored parquets + `reports/validation_summary.json` | `codetalent publish web-data` | 2026-08-03 | Dataset 2026.08.03-pilot.1; privacy scan passed; aggregate-only |
