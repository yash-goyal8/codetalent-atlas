# CodeTalent Atlas
## End-to-End Product, Data, UI, and Implementation Specification

**Document purpose:** Feed this file directly to a coding agent as the authoritative build specification.

**Project status:** All phases approved.

**Hard constraint:** The complete project must cost exactly **$0** to build, process, host, refresh, and demonstrate. Do not introduce any paid API, paid database, paid map provider, paid model, paid domain, paid hosting feature, or service that requires billing activation.

**Primary question:**

> Where should Scale investigate and build sourcing pipelines for expert contributors across high-value coding domains?

**Pilot domain:** Cloud and DevOps.

**Final product:** A polished, public, static analytical web application that ranks countries and cities using reproducible public GitHub activity data, explains every score, exposes data confidence and limitations, and produces actionable sourcing recommendations.

---

# 1. Coding Agent Operating Instructions

Treat this document as the source of truth.

1. Implement phases in numerical order.
2. Do not skip acceptance tests.
3. Do not silently change a scoring formula, threshold, data field, or UI requirement.
4. If a source field is unavailable, record the gap in `docs/decisions.md`; do not fabricate it.
5. Every data-processing step must be deterministic and rerunnable.
6. Every external response must be cached locally.
7. Never commit secrets, tokens, raw emails, or private data.
8. The public website must expose only aggregates. Do not publicly rank or display individual developers.
9. Prefer static precomputed files over a runtime backend.
10. Do not add a service that can create a charge, even if it has a free trial.
11. Use conservative API concurrency and obey all rate-limit headers.
12. After each phase, run its test suite and produce its required report before moving forward.
13. Keep a decision log at `docs/decisions.md` and a data lineage log at `docs/data_lineage.md`.
14. Pin dependencies using lockfiles.
15. The repository must work from a fresh clone using documented commands.

---

# 2. Executive Summary

Scale's coding-data products depend on access to technically capable contributors across domains such as cloud infrastructure, systems engineering, GPU computing, and security. Public developer activity is geographically distributed, but raw GitHub counts are not sufficient for a sourcing decision. Popularity, automation, duplicated forks, incomplete locations, and a few dominant repositories can distort the picture.

CodeTalent Atlas will create a directional sourcing opportunity index using:

- Public GitHub events from GH Archive queried through BigQuery Sandbox.
- GitHub GraphQL metadata for shortlisted public repositories and public user profiles.
- Offline location normalization using open datasets and curated aliases.
- Transparent repository, contributor, country, and city scoring.
- Confidence scores and bias disclosures separate from opportunity scores.
- A premium-quality static dashboard hosted free on Cloudflare Pages.

The product will not claim to measure the entire developer population. It will answer a narrower, defensible question:

> Among observable, active contributors to qualified public repositories, which locations show the strongest combination of expert supply, quality, collaboration depth, momentum, and ecosystem breadth for a selected coding domain?

---

# 3. Scope

## 3.1 Pilot scope

Build and validate the full pipeline for **Cloud and DevOps** using an initial three-month window. The implementation must be parameterized so the validated version can expand to twelve months and additional domains without redesign.

### Cloud and DevOps subdomains

1. Infrastructure as Code
2. Containers and orchestration
3. CI/CD and developer tooling
4. Observability and monitoring
5. Configuration management
6. Service mesh and networking
7. Cloud platforms and SDKs
8. SRE and reliability engineering

A repository may have multiple subdomain labels.

## 3.2 Expansion domains

After the pilot is validated, the architecture must support:

- Backend and distributed systems
- C/C++ and systems engineering
- CUDA, GPU, and performance computing
- Cybersecurity

Do not implement all expansion domains before the Cloud/DevOps pilot passes its acceptance gates.

## 3.3 Dataset targets

Pilot target:

- 10,000+ discovered candidate repositories
- 5,000+ repositories passing activity filters
- 1,000+ repositories passing full Cloud/DevOps relevance and quality filters
- 5,000+ unique non-bot contributors
- 40%+ usable country-level public locations, or a documented finding that the threshold is infeasible

Expanded target:

- 10,000-25,000 qualified repositories across all domains
- 50,000-150,000 contributor-domain records
- Country rankings for all adequately sampled locations
- City rankings only where sample size and parsing confidence are sufficient

## 3.4 Non-goals

Do not:

- Scrape GitHub HTML pages.
- Purchase or infer private contact information.
- Rank individual developers publicly.
- Claim exact labor-market size.
- Claim that GitHub users represent all developers.
- Use stars as a proxy for expertise by themselves.
- Use followers in the core expert score.
- Use a paid LLM for classification or enrichment.
- Create a live backend when static files are sufficient.
- Build a generic job marketplace.

---

# 4. Success Criteria

The project succeeds only if it delivers all of the following:

1. A credible, reproducible public-data pipeline.
2. Transparent inclusion, exclusion, and scoring rules.
3. At least three evidence-backed sourcing recommendations.
4. An interactive dashboard understandable in under two minutes.
5. A methodology page that explains every score and limitation.
6. Explicit data confidence for every country and city.
7. A public repository that can be rerun from documented commands.
8. A static public deployment at $0.
9. No individual-level public ranking.
10. Clear relevance to contributor sourcing, coding-data operations, market research, and program planning.

---

# 5. Zero-Cost Architecture

## 5.1 Data discovery

- **GH Archive public BigQuery dataset** for public GitHub event discovery.
- **BigQuery Sandbox** only; do not attach billing.
- Pilot query budget: maximum 250 GiB processed.
- Monthly free ceiling: 1 TiB processed; preserve the remaining quota.
- Store derived tables temporarily and export permanent results locally because sandbox tables expire.

## 5.2 Enrichment

- GitHub GraphQL API using a personal access token with access only to public data.
- REST API only when GraphQL cannot provide a required field.
- Authenticated REST allowance is normally 5,000 requests per hour.
- Authenticated GraphQL allowance is normally 5,000 points per hour.
- Use low concurrency, caching, checkpoints, rate-limit headers, retry-after handling, and exponential backoff.

## 5.3 Processing

- Python 3.12+
- DuckDB
- Polars or pandas; prefer Polars for large transformations when practical
- PyArrow/Parquet
- Pydantic for schemas and validation
- pytest for tests
- Ruff for linting and formatting
- mypy or pyright for static type checks

## 5.4 Location normalization

Use offline, free resources only:

- `pycountry`
- `country_converter`
- `geonamescache`
- A version-controlled alias and manual-override table
- Natural Earth country geometries for public visualization

No live geocoding API is permitted.

## 5.5 Frontend

- Vite
- React
- TypeScript
- Tailwind CSS
- shadcn/ui components
- MapLibre GL JS with a self-contained blank style and local GeoJSON layers
- Apache ECharts for analytical charts
- Framer Motion for restrained transitions
- Lucide icons
- Static JSON or compressed JSON assets generated by the pipeline

## 5.6 Hosting and automation

- Public GitHub repository
- GitHub Actions using standard hosted runners for public repositories
- Cloudflare Pages static hosting on a free `pages.dev` URL
- No Pages Functions unless essential; the intended architecture is fully static
- Keep every deployed asset below 25 MiB
- Keep total file count below 20,000
- Keep automated builds well below 500 per month

---

# 6. High-Level System Architecture

```text
GH Archive monthly tables
        |
        v
BigQuery discovery SQL
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
Offline location normalization
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
Static web datasets
        |
        v
React analytical dashboard on Cloudflare Pages
```

---

# 7. Repository Structure

Create this monorepo structure:

```text
codetalent-atlas/
├── README.md
├── AGENTS.md
├── LICENSE
├── Makefile
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
├── package.json
├── pnpm-lock.yaml
├── docs/
│   ├── product_spec.md
│   ├── methodology.md
│   ├── decisions.md
│   ├── data_lineage.md
│   ├── privacy_ethics.md
│   ├── bias_limitations.md
│   ├── research_report.md
│   └── screenshots/
├── config/
│   ├── domains.yaml
│   ├── cloud_devops_taxonomy.yaml
│   ├── repo_filters.yaml
│   ├── scoring.yaml
│   ├── bot_patterns.yaml
│   ├── location_aliases.csv
│   └── location_overrides.csv
├── sql/
│   ├── 00_profile_tables.sql
│   ├── 01_extract_events.sql
│   ├── 02_remove_bots.sql
│   ├── 03_aggregate_repositories.sql
│   ├── 04_apply_activity_filters.sql
│   ├── 05_extract_contributor_activity.sql
│   └── 06_quality_checks.sql
├── src/
│   └── codetalent/
│       ├── __init__.py
│       ├── cli.py
│       ├── settings.py
│       ├── schemas.py
│       ├── bigquery/
│       │   ├── runner.py
│       │   ├── dry_run.py
│       │   └── export.py
│       ├── github/
│       │   ├── graphql_client.py
│       │   ├── rest_client.py
│       │   ├── query_builder.py
│       │   ├── rate_limit.py
│       │   ├── checkpoints.py
│       │   └── cache.py
│       ├── classify/
│       │   ├── repository_classifier.py
│       │   ├── rules.py
│       │   └── evidence.py
│       ├── locations/
│       │   ├── normalize.py
│       │   ├── gazetteer.py
│       │   ├── confidence.py
│       │   └── aliases.py
│       ├── scoring/
│       │   ├── repository.py
│       │   ├── contributor.py
│       │   ├── geography.py
│       │   └── normalization.py
│       ├── validation/
│       │   ├── data_quality.py
│       │   ├── sampling.py
│       │   ├── bias.py
│       │   └── reports.py
│       └── publish/
│           ├── build_web_data.py
│           ├── compress.py
│           └── manifest.py
├── scripts/
│   ├── setup_bigquery.sh
│   ├── run_discovery.py
│   ├── enrich_repositories.py
│   ├── enrich_users.py
│   ├── normalize_locations.py
│   ├── calculate_scores.py
│   ├── validate_dataset.py
│   └── build_web_assets.py
├── data/
│   ├── README.md
│   ├── raw/.gitkeep
│   ├── cache/.gitkeep
│   ├── interim/.gitkeep
│   ├── processed/.gitkeep
│   ├── samples/
│   └── public/
├── reports/
│   ├── query_usage.csv
│   ├── enrichment_usage.csv
│   ├── discovery_validation.md
│   ├── classification_validation.csv
│   ├── location_validation.csv
│   ├── ranking_validation.md
│   └── data_dictionary.md
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── snapshots/
├── web/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── public/
│   │   ├── data/
│   │   ├── geo/
│   │   └── social-card.png
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── routes/
│       ├── components/
│       ├── features/
│       ├── hooks/
│       ├── lib/
│       ├── styles/
│       └── types/
└── .github/
    └── workflows/
        ├── ci.yml
        ├── refresh-data.yml
        └── deploy.yml
```

`data/raw`, `data/cache`, and full user-level processed files must be gitignored. Commit only small samples and aggregate public assets.

---

# 8. Configuration Contracts

## 8.1 `config/cloud_devops_taxonomy.yaml`

```yaml
domain_id: cloud_devops
display_name: Cloud and DevOps
subdomains:
  infrastructure_as_code:
    display_name: Infrastructure as Code
    positive_topics: [terraform, pulumi, infrastructure-as-code, iac, cloudformation]
    positive_terms: [terraform, pulumi, cloudformation, infrastructure as code, provisioning]
    positive_files: ["*.tf", "Pulumi.yaml", "template.yaml"]
    negative_terms: [tutorial, interview questions, awesome list]

  containers_orchestration:
    display_name: Containers and Orchestration
    positive_topics: [kubernetes, docker, containers, helm, operator]
    positive_terms: [kubernetes, docker, container runtime, helm chart, operator]
    positive_files: [Dockerfile, "Chart.yaml", "values.yaml"]

  cicd_developer_tooling:
    display_name: CI/CD and Developer Tooling
    positive_topics: [ci-cd, github-actions, jenkins, build-system, developer-tools]
    positive_terms: [continuous integration, continuous delivery, build pipeline, release automation]
    positive_files: [".github/workflows/*.yml", "Jenkinsfile", ".gitlab-ci.yml"]

  observability_monitoring:
    display_name: Observability and Monitoring
    positive_topics: [observability, monitoring, tracing, metrics, logging, opentelemetry]
    positive_terms: [observability, distributed tracing, monitoring, metrics, logging]

  configuration_management:
    display_name: Configuration Management
    positive_topics: [ansible, chef, puppet, configuration-management]
    positive_terms: [configuration management, ansible, chef, puppet]

  service_mesh_networking:
    display_name: Service Mesh and Networking
    positive_topics: [service-mesh, networking, envoy, istio, proxy]
    positive_terms: [service mesh, networking, load balancing, proxy, ingress]

  cloud_platforms_sdks:
    display_name: Cloud Platforms and SDKs
    positive_topics: [aws, azure, google-cloud, cloud-sdk, serverless]
    positive_terms: [cloud sdk, aws, azure, google cloud, serverless]

  sre_reliability:
    display_name: SRE and Reliability Engineering
    positive_topics: [sre, reliability, incident-response, chaos-engineering]
    positive_terms: [site reliability, incident response, chaos engineering, resilience]
```

The final configuration must expand each list substantially and include tests proving known positive and negative examples.

## 8.2 `config/repo_filters.yaml`

```yaml
activity_window:
  pilot_start: "2026-05-01"
  pilot_end: "2026-07-31"
  expanded_months: 12

minimums:
  unique_human_contributors: 5
  meaningful_events: 20
  pull_requests_or_reviews: 3
  active_months: 2

requirements:
  must_be_public: true
  must_not_be_fork: true
  must_not_be_archived: true
  must_not_be_disabled: true
  require_recognized_license: true
  require_recent_activity: true

exclusions:
  tutorial_only: true
  dotfiles: true
  student_assignments: true
  interview_prep: true
  awesome_lists: true
  documentation_only: true
  mirrors: true
  generated_copies: true
  single_contributor_dominance_threshold: 0.90
```

## 8.3 `config/scoring.yaml`

Store all weights, clipping rules, and minimum sample thresholds in configuration. No scoring weight may exist only in source code.

---

# 9. Core Data Schemas

Implement Pydantic models and matching Parquet schemas.

## 9.1 Repository activity summary

```text
repo_name: string
owner_login: string
repo_short_name: string
unique_human_contributors: int
active_days: int
active_months: int
push_events: int
push_commit_count: int
pull_requests_opened: int
pull_requests_closed: int
merged_pull_requests: int
reviews_submitted: int
issues_opened: int
issue_comments: int
releases: int
weighted_activity_score: float
first_seen: date
last_seen: date
automation_event_share: float
single_actor_event_share: float
discovery_status: string
exclusion_reason: nullable string
```

## 9.2 Repository metadata

```text
repo_name: string
description: nullable string
is_fork: bool
is_archived: bool
is_disabled: bool
primary_language: nullable string
topics: list[string]
stargazer_count: int
fork_count: int
license_spdx_id: nullable string
pushed_at: nullable datetime
updated_at: nullable datetime
release_count: int
issue_count: int
pull_request_count: int
has_readme: nullable bool
has_contributing: nullable bool
has_code_of_conduct: nullable bool
has_ci: nullable bool
has_tests_signal: nullable bool
graphql_fetched_at: datetime
```

## 9.3 Repository classification

```text
repo_name: string
domain_id: string
subdomains: list[string]
classification_score: float
classification_status: enum[accepted, rejected, borderline]
evidence_topics: list[string]
evidence_terms: list[string]
evidence_files: list[string]
negative_evidence: list[string]
manual_label: nullable string
manual_notes: nullable string
```

## 9.4 Contributor activity

```text
actor_login: string
repo_name: string
domain_id: string
subdomains: list[string]
push_events: int
pull_requests_opened: int
merged_pull_requests_authored: int
reviews_submitted: int
issues_opened: int
issue_comments: int
active_days: int
active_months: int
first_seen: date
last_seen: date
raw_contribution_points: float
```

## 9.5 Public user profile enrichment

```text
actor_login: string
account_type: enum[user, bot, organization, unknown]
public_location_raw: nullable string
created_at: nullable datetime
followers_count: nullable int
profile_fetched_at: datetime
fetch_status: enum[success, not_found, rate_limited, error]
```

Do not collect or store public email, employer, website, or name unless a later research requirement is explicitly approved. They are unnecessary for geographic aggregation.

## 9.6 Normalized location

```text
actor_login: string
raw_location: nullable string
normalized_country_code: nullable string
normalized_country_name: nullable string
normalized_city: nullable string
latitude: nullable float
longitude: nullable float
location_level: enum[city, country, region, unknown]
location_confidence: enum[high, medium, low, unusable]
normalization_method: enum[exact_alias, parsed_country, unique_city, city_country_pair, manual_override, unresolved]
ambiguity_reason: nullable string
```

## 9.7 Contributor score

```text
actor_login: string
domain_id: string
expert_score: float
domain_activity_score: float
contribution_quality_score: float
repository_quality_exposure_score: float
continuity_score: float
collaboration_score: float
qualified_repo_count: int
active_months: int
country_code: nullable string
city: nullable string
location_confidence: string
```

## 9.8 Geographic ranking

```text
geo_level: enum[country, city]
geo_id: string
country_code: string
city: nullable string
domain_id: string
opportunity_score: float
confidence_score: float
expert_supply_score: float
expert_quality_score: float
collaboration_depth_score: float
momentum_score: float
ecosystem_breadth_score: float
observable_expert_count: int
weighted_expert_count: float
qualified_repo_count: int
organization_count: int
multi_repo_expert_share: float
located_profile_coverage: float
high_confidence_location_share: float
top_subdomains: list[string]
rank: int
recommendation_tier: enum[priority, promising, monitor, insufficient_data]
```

---

# 10. Phase 0 - Product Definition

## Objective

Lock the core question, user, scope, zero-cost constraint, and final deliverables.

## Deliverables

- `docs/product_spec.md`
- `docs/privacy_ethics.md`
- `config/domains.yaml`
- This build specification copied into the repository

## Acceptance criteria

- Core question appears consistently in README and product documentation.
- Cloud/DevOps is the only pilot domain.
- Public output is aggregate-only.
- $0 constraint is explicitly documented.

---

# 11. Phase 1 - Data Source Feasibility Pilot

## Objective

Prove that the free data architecture can produce enough repositories, contributors, and usable locations.

## Tasks

1. Create a BigQuery Sandbox project without billing.
2. Confirm access to `githubarchive` monthly tables.
3. Dry-run a small query over one day.
4. Query three pilot months using only required columns.
5. Produce a 1,000-repository candidate sample.
6. Extract up to 10,000 unique contributor logins from relevant activity.
7. Enrich a representative sample of 1,000 public profiles using GraphQL aliases.
8. Measure public-location availability and GraphQL point usage.
9. Record errors, missing profiles, bots, and location coverage.

## Required report

`reports/feasibility.md` must include:

- BigQuery bytes processed
- Query runtime
- Candidate repository count
- Unique actor count
- Bot share
- GraphQL points used
- Profile fetch success rate
- Non-empty location rate
- Country-normalizable rate
- City-normalizable rate
- Recommendation to proceed or adjust

## Acceptance criteria

- 1,000 candidate repositories discovered.
- 5,000 non-bot actors available in the sample or a documented reason the threshold is not met.
- 40% usable country-level locations is the target, not a fact to assume.
- No scraping.
- No paid service.
- All responses cached and rerunnable.

---

# 12. Phase 2 - Repository Taxonomy and Selection Rules

## Objective

Define which repositories are genuinely relevant, active, collaborative, and production-oriented.

## Classification method

Use transparent weighted rules based on:

- Repository topics
- Description and name terms
- Primary language
- Domain-specific files or configuration signals
- Negative terms and exclusion patterns

Do not use a paid or hosted LLM. A local open model is also unnecessary for the MVP; use deterministic rules first.

## Inclusion rules

A repository must be:

- Public
- Not a fork
- Not archived or disabled
- Active within the selected window
- Associated with at least five unique human contributors
- Associated with at least twenty meaningful events
- Associated with at least three pull requests or reviews
- Active in at least two months during the three-month pilot
- Clearly related to at least one Cloud/DevOps subdomain
- Covered by a recognized open-source license

## Exclusion rules

Exclude:

- Bots and automation accounts
- Dotfiles
- Tutorial-only projects
- Student assignments
- Interview-preparation repositories
- Awesome lists
- Documentation-only repositories
- Mirrors and generated copies
- Abandoned repositories
- Repositories where one actor accounts for more than 90% of meaningful activity
- Repositories with suspicious burst patterns
- Repositories unrelated to production engineering

## Manual validation

Create a stratified set of 150 repositories:

- 50 automatically accepted
- 50 automatically rejected
- 50 borderline

Label each manually using a documented rubric.

## Acceptance criteria

- Domain-classification precision >= 90% on the reviewed sample.
- False inclusion rate < 10%.
- Every Cloud/DevOps subdomain has at least 100 qualified repositories after expansion, or the report explains why not.
- No single organization contributes more than 10% of the final qualified repository sample without an explicit concentration warning.

---

# 13. Phase 3 - Large-Scale Repository Discovery

## Objective

Use GH Archive and BigQuery to discover active repositories at scale before GitHub API enrichment.

## Pilot window

Default approved window:

- Start: 2026-05-01
- End: 2026-07-31

Parameterize dates through CLI flags and configuration. The expanded run should use the latest twelve complete months.

## Relevant event types

- PushEvent
- PullRequestEvent
- PullRequestReviewEvent
- IssuesEvent
- IssueCommentEvent
- ReleaseEvent

## Event weights

```text
Merged pull request: 5
Pull-request review: 4
Pull request opened: 3
Release: 3
Push event: 2
Issue opened or commented: 1
```

## BigQuery requirements

1. Every query must support a dry run.
2. Every query must set a maximum bytes processed guard.
3. Record estimated and actual bytes in `reports/query_usage.csv`.
4. Avoid `SELECT *` in production SQL.
5. Materialize intermediate aggregates to avoid repeated scans.
6. `LIMIT` is not a cost-control mechanism.
7. Preserve raw and human-filtered aggregates for auditability.

## Bot patterns

At minimum include:

- Login ending in `[bot]`
- `dependabot`
- `renovate`
- `github-actions`
- `codecov`
- `snyk-bot`
- Common CI release bots

Keep bot detection configuration external and record excluded counts by pattern.

## Output

- `data/interim/repository_activity_summary.parquet`
- `data/interim/cloud_devops_repository_candidates.parquet`
- `reports/query_usage.csv`
- `reports/discovery_validation.md`

## Acceptance criteria

- 10,000+ candidates discovered.
- 5,000+ pass first-stage activity filters.
- Phase query usage <= 250 GiB.
- Bot removals are auditable.
- High, random, and low accepted samples appear valid.

---

# 14. Phase 4 - GitHub Repository and User Enrichment

## Objective

Fetch only the metadata unavailable in GH Archive, while staying within free GitHub limits and avoiding blocks.

## Authentication

- Use `GITHUB_TOKEN` from environment variables locally.
- Use a repository secret only for GitHub Actions.
- Never expose the token to the frontend.
- Request no permissions beyond public-read requirements.

## Repository GraphQL batching

Generate alias-based GraphQL queries. Start with 10 repositories per request and adapt upward only after measuring query cost and response size. Do not assume 50 is always safe.

Fetch:

- `isFork`
- `isArchived`
- `isDisabled`
- `description`
- `primaryLanguage { name }`
- `repositoryTopics(first: 20)`
- `stargazerCount`
- `forkCount`
- `licenseInfo { spdxId }`
- `pushedAt`
- `updatedAt`
- release count
- issue count
- pull-request count

Optional lightweight content checks may use REST raw-content requests for a small shortlist only:

- README existence
- CONTRIBUTING existence
- CODE_OF_CONDUCT existence
- CI configuration presence
- Test-directory or test-file signal

Do not clone thousands of repositories.

## User GraphQL batching

Fetch only:

- Login
- Account type where resolvable
- Public location
- Account creation date
- Followers count for descriptive analysis only

Do not fetch public emails or names.

## Rate-limit behavior

The client must:

1. Read `rateLimit` data in GraphQL responses.
2. Read REST rate-limit headers.
3. Pause before the remaining budget is exhausted.
4. Obey `Retry-After`.
5. Retry 403/429 only according to documented reset/backoff rules.
6. Use exponential backoff with jitter.
7. Limit concurrency to a conservative default of 2.
8. Save a checkpoint after every successful batch.
9. Cache each response by normalized request hash.
10. Resume without refetching completed records.

## Cache design

```text
data/cache/github/graphql/repositories/<hash>.json
data/cache/github/graphql/users/<hash>.json
data/cache/github/rest/<endpoint_hash>.json
data/interim/checkpoints/repositories.json
data/interim/checkpoints/users.json
```

## Required usage report

`reports/enrichment_usage.csv`:

```text
timestamp, resource_type, batch_size, query_cost, remaining, reset_at, status, retries, cache_hit
```

## Acceptance criteria

- 95%+ successful repository enrichment excluding deleted/private transitions.
- 90%+ successful user lookup for still-existing public accounts.
- No duplicated calls after resume.
- No sustained 403/429 behavior.
- No concurrency above configured safe limits.
- All raw responses cached locally and gitignored.

---

# 15. Phase 5 - Offline Location Normalization

## Objective

Convert free-form public GitHub locations into defensible country and city labels without a paid geocoder.

## Normalization pipeline

Process in this order:

1. Null and placeholder removal: `Earth`, `Internet`, `Remote`, emojis, jokes, empty strings.
2. Unicode normalization and whitespace cleanup.
3. Exact manual override.
4. Exact alias match.
5. Explicit ISO country code or country-name match.
6. City-country pair match.
7. Unique globally recognizable city match.
8. Region/state plus country resolution.
9. Ambiguity detection.
10. Unresolved output.

## Confidence rules

### High

- Explicit unambiguous country.
- Exact curated city-country pair.
- Manual override with documented evidence.

### Medium

- Unique city name with one dominant global match.
- State/region and country combination.

### Low

- Ambiguous city with heuristic resolution.
- Broad region only.

### Unusable

- Joke, virtual location, multiple conflicting locations, or unresolved text.

## Aggregation eligibility

- Country rankings: high and medium country matches.
- City rankings: high-confidence city matches only.
- Low-confidence matches may be shown only in coverage diagnostics, never counted in the main ranking.

## Privacy

The public dataset must never expose `actor_login -> normalized_location`. Publish only aggregates. Raw user-level normalization remains local and gitignored.

## Validation sample

Manually review at least 500 stratified location strings:

- Common successful parses
- Ambiguous cities
- Non-English locations
- Abbreviations
- Failure cases

## Acceptance criteria

- Country precision >= 95% on high-confidence labels.
- City precision >= 90% on high-confidence labels.
- Every manual override has a note.
- Ambiguous cases are not silently forced.
- Public assets contain no usernames.

---

# 16. Phase 6 - Repository and Contributor Scoring

## 16.1 Repository quality score

Calculate a 0-100 score:

```text
Repository Quality =
30% Recent Activity
+ 25% Contributor Diversity
+ 20% Collaboration Quality
+ 15% Technical Relevance
+ 10% Repository Maturity
```

### Recent Activity

Signals:

- Active months
- Active days
- Recency of last event
- Releases
- Weighted activity, log-scaled

### Contributor Diversity

Signals:

- Unique human contributors
- One-actor concentration penalty
- Recurring contributor share
- New contributor share

### Collaboration Quality

Signals:

- Merged pull requests
- Reviews
- Review-to-PR ratio
- Multi-person issue participation

### Technical Relevance

Signals:

- Taxonomy match score
- Topic matches
- Description/name matches
- Domain-file evidence
- Negative-evidence penalty

### Repository Maturity

Signals:

- Recognized license
- Releases
- CI signal
- Tests signal
- CONTRIBUTING or governance documentation

Use robust scaling and clipping. Avoid letting a single huge repository set the scale for every other repository. Prefer percentile ranks, `log1p`, winsorization at the 99th percentile, and bounded subscores.

## 16.2 Contributor expert score

Calculate a 0-100 domain-specific score:

```text
Expert Score =
35% Domain Activity
+ 25% Contribution Quality
+ 20% Repository Quality Exposure
+ 10% Continuity
+ 10% Collaboration
```

### Domain Activity

- Domain-weighted event points
- Number of qualified repositories
- Subdomain breadth

### Contribution Quality

Use event-type evidence:

- Merged pull requests authored
- Reviews submitted
- Pull requests opened
- Push activity, capped to reduce bulk-commit distortion
- Issues, low weight

Do not claim code quality from event counts. Call this component contribution quality evidence, not intrinsic developer quality.

### Repository Quality Exposure

Weighted average of the quality scores of repositories where the contributor was active. Cap the influence of any one repository.

### Continuity

- Active months
- Repeat activity across the window
- Recency

### Collaboration

- Reviews
- Pull-request participation
- Activity across multiple repositories and organizations

## Bias safeguards

- Do not use followers in the expert score.
- Cap contribution from one repository at 40% of a contributor's score.
- Cap the influence of raw push volume.
- Require at least two meaningful active days.
- Mark one-repository contributors separately.
- Keep raw and weighted counts.

## Acceptance criteria

- Score components sum exactly to configured totals.
- Scores are deterministic.
- Snapshot tests cover known examples.
- Distribution reports show no obvious single-signal domination.
- Manual review of top, middle, and low scores is sensible.

---

# 17. Phase 7 - Country and City Opportunity Ranking

## Objective

Translate contributor and repository evidence into actionable location rankings.

## Opportunity score

Calculate separately by domain and geography:

```text
Opportunity Score =
35% Expert Supply
+ 30% Expert Quality
+ 15% Collaboration Depth
+ 10% Momentum
+ 10% Ecosystem Breadth
```

### Expert Supply

- Weighted unique contributor count
- Log-scaled
- Contributors weighted by expert score, but capped so a few elites do not replace supply

### Expert Quality

- Weighted median expert score
- Top-quartile expert share
- Avoid simple average sensitivity

### Collaboration Depth

- Multi-repository expert share
- Review participation
- Recurring contributor share

### Momentum

For the expanded twelve-month dataset:

- Latest three-month activity compared with the previous three months
- New qualified contributors
- New qualified repositories

For the three-month pilot, label momentum as provisional and use month-over-month direction only.

### Ecosystem Breadth

- Qualified repository count
- Distinct organization count
- Subdomain breadth
- Concentration penalty

## Confidence score

Confidence must be separate from opportunity:

```text
Confidence Score =
35% Located Profile Coverage
+ 25% Location Certainty
+ 20% Sample Size Adequacy
+ 10% Repository Diversity
+ 10% Organization Diversity
```

A high opportunity score with low confidence must not be labeled a priority recommendation.

## Minimum sample rules

Country:

- Minimum 30 located contributors
- Minimum 10 qualified repositories
- Minimum 5 organizations

City:

- Minimum 25 high-confidence located contributors
- Minimum 8 qualified repositories
- Minimum 4 organizations

Below the threshold, label `insufficient_data` and do not assign a normal rank.

## Recommendation tiers

```text
Priority:
  Opportunity >= 75 and Confidence >= 70

Promising:
  Opportunity >= 60 and Confidence >= 60

Monitor:
  Opportunity >= 45 or Confidence between 45 and 59

Insufficient data:
  Sample rule failed or Confidence < 45
```

## Concentration safeguards

- Cap any single repository's contribution to a geography's weighted supply.
- Flag any organization contributing > 20% of a location's weighted activity.
- Show raw count and weighted count.
- Include a concentration-risk indicator.

## Acceptance criteria

- Every displayed ranking can be reconstructed from published methodology.
- Opportunity and confidence are never merged into one opaque score.
- Tier rules are configuration-driven.
- No low-sample city appears as a top recommendation.

---

# 18. Phase 8 - Validation, Bias, and Research Integrity

## Objective

Prove the dataset is useful while clearly stating what it cannot measure.

## Validation layers

### Data quality

- Nulls
- Duplicates
- Referential integrity
- Schema compliance
- Date bounds
- Score bounds
- Aggregate totals

### Repository classification

- Precision and false-inclusion rate from the 150-repository sample

### Location accuracy

- Country and city precision from the 500-location sample

### Ranking stability

Run sensitivity tests:

- Remove the top 1% of repositories by activity.
- Remove the largest organization per country.
- Vary score weights by +/- 20%.
- Compare three-month and twelve-month windows.
- Compare raw and weighted contributor counts.

Report locations whose rank changes materially.

### Coverage bias

Measure:

- Missing public-location rate
- Location coverage by activity decile
- Coverage by primary language
- Coverage by organization size
- Country-name and English-language parsing bias

### Representation limitations

Document:

- GitHub activity is not the total developer workforce.
- Public contribution behavior differs by region and employer.
- Self-reported locations may be missing, stale, humorous, or ambiguous.
- Event volume does not directly measure engineering quality.
- Open-source expertise may not equal availability or willingness to contract.
- Some domains are underrepresented in public repositories.

## Required outputs

- `reports/ranking_validation.md`
- `docs/bias_limitations.md`
- Sensitivity CSVs
- Coverage charts for the methodology page

## Acceptance criteria

- No recommendation is published without a confidence score.
- Rankings are reasonably stable or instability is clearly disclosed.
- Limitations are visible in the product, not hidden only in the repository.

---

# 19. Phase 9 - UI/UX Design Specification

## Product personality

The interface should feel like a premium strategy and market-intelligence product, not a hackathon dashboard.

Keywords:

- Precise
- Analytical
- Technical
- Calm
- High contrast
- Data-dense but uncluttered
- Executive-ready

## Visual system

### Theme

- Dark default theme
- Near-black navy background, not pure black
- Cool gray surfaces
- One electric accent for selected states
- Semantic positive, warning, and risk colors
- No rainbow map by default

Suggested tokens:

```text
background: #070A12
surface-1: #0D1220
surface-2: #121A2B
border: rgba(255,255,255,0.08)
text-primary: #F4F7FB
text-secondary: #9BA8BC
accent: #6D8BFF
positive: #36C98F
warning: #F2B84B
risk: #F06B7A
```

The coding agent may refine shades for accessibility but must preserve the character.

### Typography

Use an open-source web font bundled or loaded through a free public source. Prefer a modern sans family such as Geist or Inter. Use tabular numerals for scores.

### Layout

- Desktop-first analytical canvas
- Maximum content width around 1600px
- 12-column grid
- Sticky global filter bar
- Responsive tablet and mobile adaptations
- Avoid tiny text below 12px

## Core routes

```text
/                       Executive overview
/explore                Interactive geographic explorer
/compare                Compare up to four locations
/location/:geoId        Country or city detail
/methodology            Data, scoring, validation, limitations
/recommendations        Executive sourcing recommendations
/about                   Project purpose and author context
```

## 19.1 Executive overview

Above the fold:

- Product title: CodeTalent Atlas
- One-line value proposition
- Domain selector
- Data-window label
- Four KPI cards:
  - Qualified repositories
  - Observable experts
  - Located-profile coverage
  - Countries with sufficient data
- Interactive globe preview
- Top five priority locations

Below:

- Opportunity vs confidence scatterplot
- Top subdomain hubs
- Methodology summary
- Three evidence-backed recommendations
- Prominent limitations note

## 19.2 Explorer

Desktop layout:

```text
[Sticky domain/subdomain/time filters]
[Map or globe: 65%] [Ranked location rail: 35%]
[Score breakdown and trend panels below]
```

Map behavior:

- Country choropleth by opportunity score
- Confidence displayed through opacity, border, or hatch treatment
- City points sized by observable expert count
- Hover tooltip with rank, opportunity, confidence, supply, and top subdomain
- Click opens side panel; second click opens detail route
- Toggle between country and city views
- Toggle between opportunity, supply, quality, momentum, and confidence layers

Do not use live paid map tiles. Use local Natural Earth country GeoJSON and a blank MapLibre style.

## 19.3 Ranked location rail

Each row includes:

- Rank
- Country/city name
- Opportunity score
- Confidence score
- Observable expert count
- Top subdomain
- Recommendation tier
- Rank-change indicator when available

Filters:

- Domain
- Subdomain
- Country/city level
- Minimum confidence
- Recommendation tier
- Search

## 19.4 Location detail page

Hero:

- Location name and flag
- Opportunity score
- Confidence score
- Tier
- Concise recommendation statement

Sections:

1. Score decomposition radar or horizontal bars
2. Observable expert supply and quality distribution
3. Activity trend
4. Subdomain mix
5. Repository and organization breadth
6. Concentration risk
7. Why this location ranks here
8. Data coverage and caveats
9. Compare button

Do not expose developer usernames.

## 19.5 Compare page

Allow two to four locations.

Show:

- Opportunity and confidence side by side
- Score-component bars
- Expert supply
- Expert quality distribution
- Subdomain strengths
- Momentum
- Ecosystem breadth
- Coverage and concentration risks
- Auto-generated factual comparison summary assembled from templates, not an API model

## 19.6 Methodology page

Must be visually strong, not a text dump.

Include:

- Pipeline diagram
- Data funnel
- Inclusion/exclusion rules
- Repository score formula
- Contributor score formula
- Opportunity and confidence formulas
- Location coverage chart
- Validation results
- Sensitivity-analysis summary
- Limitations
- Data freshness
- Download aggregate data button

## 19.7 Recommendations page

Create an executive memo layout:

- Top three recommended sourcing pilots
- Why now
- Relevant subdomains
- Observable pool size
- Confidence
- Main risk
- Suggested pilot action

Template example:

```text
Investigate [Location] for [Subdomain] contributors.
Evidence: [supply], [quality], [breadth], [momentum].
Confidence: [score and reason].
Risk: [coverage or concentration issue].
Suggested next step: run a small sourcing pilot and validate response and qualification rates.
```

## Interaction and motion

- 150-250 ms transitions
- Respect `prefers-reduced-motion`
- Smooth map and panel transitions
- Skeleton loading for static data chunks
- No decorative animation that delays analysis

## Accessibility

- WCAG AA contrast
- Keyboard-accessible filters and dialogs
- Visible focus indicators
- Semantic headings
- ARIA labels for charts and map controls
- Text alternatives and accessible tabular fallback for key visualizations
- Do not rely on color alone for confidence or tiers

## Responsive behavior

Mobile:

- Map above ranked list
- Bottom-sheet location details
- Simplified charts
- Sticky domain selector
- Compare limited to two locations

## Empty/error states

Provide designed states for:

- No locations matching confidence filters
- Insufficient city data
- Data file load failure
- No trend data for pilot
- Unsupported domain

## UI acceptance criteria

- Lighthouse performance >= 90 on desktop target build.
- Lighthouse accessibility >= 95.
- No deployed asset > 25 MiB.
- Main route interactive within 3 seconds on a typical broadband connection.
- All routes work without a server backend.
- A user can identify the top location and understand why within two minutes.

---

# 20. Phase 10 - Frontend Implementation

## Static data contract

Generate files under `web/public/data/`:

```text
manifest.json
summary.json
domains.json
rankings/cloud_devops/countries.json
rankings/cloud_devops/cities.json
locations/countries/<country_code>.json
locations/cities/<slug>.json
compare/cloud_devops.json
methodology/validation.json
methodology/coverage.json
recommendations/cloud_devops.json
```

## Manifest example

```json
{
  "datasetVersion": "2026.08.01-pilot.1",
  "generatedAt": "2026-08-01T23:00:00Z",
  "window": {"start": "2026-05-01", "end": "2026-07-31"},
  "domains": ["cloud_devops"],
  "files": {
    "summary": "summary.json",
    "countryRankings": "rankings/cloud_devops/countries.json"
  },
  "methodologyVersion": "1.0.0"
}
```

## State management

Use lightweight React state and URL search parameters. Avoid a large state-management library unless necessary.

Persistent URL state:

- domain
- subdomain
- geo level
- score layer
- minimum confidence
- selected locations

## Chart requirements

- ECharts configurations must be typed.
- Tooltips must contain units and methodology hints.
- Charts must have accessible summaries.
- Use consistent score scales from 0 to 100.

## Map requirements

- Local country GeoJSON.
- Local city centroid coordinates from normalized aggregate output.
- No external API key.
- Cluster city points when zoomed out.
- Lazy-load city data.

## Performance

- Code-split routes.
- Lazy-load MapLibre.
- Compress JSON at build time where supported by hosting.
- Split city detail files.
- Memoize expensive transformations.
- Virtualize long ranking lists if necessary.

## Testing

- Vitest for utilities and components.
- React Testing Library for key interactions.
- Playwright for end-to-end flows.
- Screenshot tests for main routes at desktop and mobile dimensions.

## Required E2E flows

1. Load overview and select Cloud/DevOps.
2. Open explorer and filter to Observability.
3. Select a country from the map.
4. Open its detail page.
5. Add it to compare.
6. Add a second location.
7. Navigate to methodology and inspect score definitions.
8. Verify no username appears anywhere in the public UI.

---

# 21. Phase 11 - Testing and Performance

## Python quality gates

```text
ruff check .
ruff format --check .
pytest
mypy src
```

## Data contracts

Test:

- Uniqueness of primary keys
- No impossible negative counts
- Score range 0-100
- Ranking order consistency
- Tier and threshold consistency
- Country-code validity
- Public files contain no usernames
- Public files contain no raw locations
- All map geo IDs resolve

## Frontend quality gates

```text
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm playwright test
```

## Performance gates

- Inspect bundle size.
- Main JS target under 500 KiB compressed where practical, with MapLibre isolated in a lazy chunk.
- Country ranking payload under 1 MiB.
- Individual city-detail payloads under 250 KiB.
- All assets below Cloudflare's per-file limit.

## Visual QA

Review:

- 1440x900
- 1280x800
- 768x1024
- 390x844

Check:

- No clipping or overlap
- Map controls usable
- Tables scroll correctly
- Tooltips do not leave viewport
- Dark-theme contrast
- Reduced-motion mode

---

# 22. Phase 12 - Free Deployment and Refresh Pipeline

## Cloudflare Pages deployment

Build command:

```bash
pnpm --dir web build
```

Output directory:

```text
web/dist
```

Use a `pages.dev` subdomain. Do not purchase a custom domain.

## GitHub Actions

### `ci.yml`

On pull request and main push:

- Python lint, type check, and tests
- Frontend lint, type check, tests, and build
- Public-data privacy scan

### `refresh-data.yml`

Manual dispatch by default for the pilot. Scheduled refresh may be monthly after the pipeline is stable.

Steps:

1. Validate required secrets.
2. Run BigQuery discovery only if explicitly enabled.
3. Resume GitHub enrichment from cache/checkpoint.
4. Normalize and score.
5. Validate public outputs.
6. Build public aggregate data.
7. Open a pull request containing only aggregate updates and reports.

Important: A GitHub Actions `GITHUB_TOKEN` has a lower API rate limit per repository than a normal user token. For large enrichment runs, prefer a manually triggered local process using a personal token, then commit only aggregates. Do not design a workflow that repeatedly exhausts API quotas.

### `deploy.yml`

Prefer Cloudflare's native Git integration. If a workflow is used, keep credentials in repository secrets and deploy static output only.

## Refresh policy

Pilot:

- One frozen dataset version for the application and report.

Post-pilot:

- Monthly refresh.
- Preserve previous aggregate versions for rank-change analysis.
- Do not refetch unchanged repository/user metadata before its cache TTL.

Suggested TTLs:

- Repository metadata: 30 days
- User location: 90 days
- Deleted/not-found user: 30 days
- Taxonomy classification: until taxonomy version changes

## Versioning

```text
Dataset version: YYYY.MM.DD-<scope>.<revision>
Methodology version: semantic version
Taxonomy version: semantic version
```

Display dataset date and methodology version in the UI footer and methodology page.

---

# 23. Phase 13 - Research Report and Application Packaging

## Research report structure

`docs/research_report.md`:

1. Executive summary
2. Business question
3. Why public open-source activity is directionally useful
4. Data sources
5. Repository taxonomy
6. Data funnel
7. Scoring methodology
8. Validation
9. Findings
10. Recommended sourcing pilots
11. Sensitivity analysis
12. Biases and limitations
13. Next steps

## Required findings format

Do not pre-write conclusions. Generate after the validated dataset exists.

For each recommended location:

- Domain/subdomain
- Opportunity score
- Confidence score
- Observable expert count
- Repository and organization breadth
- Momentum
- Main caveat
- Suggested sourcing experiment

## Demo flow under two minutes

1. State the question.
2. Show the data funnel and $0 public-data method.
3. Select a subdomain.
4. Show the top location.
5. Explain the score and confidence separately.
6. Compare with another location.
7. End with three recommended sourcing pilots and limitations.

## Resume bullet template

Use only after real results exist:

> Built CodeTalent Atlas, a public-data sourcing intelligence product analyzing [X] qualified repositories and [Y] observable contributors to identify high-potential global hubs for expert coding-data programs; designed transparent opportunity and confidence scores, validated geographic and classification accuracy, and deployed an interactive dashboard at $0 cost.

Do not insert invented X or Y values.

## Outreach positioning

> I investigated where Scale could expand sourcing for specialized coding contributors using only public GitHub activity. I built a reproducible pipeline that distinguishes expert supply from data confidence and converts repository and contributor evidence into location-level sourcing recommendations.

---

# 24. CLI Requirements

Implement a Typer CLI:

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

`codetalent pipeline pilot` must execute all safe local stages in sequence and stop with a clear message when external credentials or BigQuery execution are required.

---

# 25. Environment Variables

`.env.example`:

```bash
GITHUB_TOKEN=
GOOGLE_CLOUD_PROJECT=
BIGQUERY_LOCATION=US
BIGQUERY_MAX_BYTES_PHASE3=268435456000
DATASET_ID=codetalent_atlas
CACHE_DIR=data/cache
LOG_LEVEL=INFO
```

Never require a Cloudflare API token if native Git deployment is used.

---

# 26. Logging, Checkpoints, and Failure Handling

## Structured logs

Log JSON lines for pipeline runs:

```text
run_id
phase
step
status
records_in
records_out
cache_hits
api_cost
bytes_processed
duration_seconds
error_type
```

## Checkpointing

Every long-running enrichment job must checkpoint:

- Completed IDs
- Failed IDs
- Retry count
- Last rate-limit state
- Current batch size

## Failure policy

- Invalid configuration: fail immediately.
- BigQuery dry-run over budget: fail before execution.
- 401 authentication: fail immediately with setup instructions.
- 403/429 rate limit: pause according to headers, then retry conservatively.
- Repeated secondary limit: stop and preserve checkpoint.
- Malformed record: quarantine to an error file; do not stop the entire run unless error rate exceeds 1%.
- Public privacy scan failure: block build and deployment.

---

# 27. Public Data Privacy Scanner

Create a test that recursively scans `web/public/data` and `data/public` for prohibited fields and patterns.

Prohibited:

- `actor_login`
- `user_login`
- GitHub profile URL
- Raw location string
- Email addresses
- Names
- API tokens

Allowed:

- Aggregate counts
- Country/city names
- Scores
- Repository counts
- Organization counts
- Subdomain summaries

The deployment pipeline must fail if prohibited content is found.

---

# 28. Data Quality Test Matrix

| Layer | Test | Failure behavior |
|---|---|---|
| GH Archive | Date bounds correct | Stop |
| GH Archive | No duplicate event IDs where IDs exist | Stop |
| Bot filter | Excluded pattern counts recorded | Warn/stop if missing |
| Repositories | Primary key unique | Stop |
| Repositories | Thresholds applied consistently | Stop |
| Classification | Evidence present for accepted record | Stop |
| GitHub enrichment | Cache/checkpoint integrity | Stop |
| Locations | Country code valid | Quarantine |
| Locations | City coordinate valid | Quarantine |
| Scores | Components in 0-100 | Stop |
| Scores | Weighted sum matches final | Stop |
| Rankings | Minimum samples enforced | Stop |
| Public data | No individual identifiers | Stop deployment |
| Frontend | Every geo ID resolves | Stop build |

---

# 29. Recommended Implementation Order for the Coding Agent

## Milestone A - Repository foundation

- Create monorepo structure.
- Add Python and frontend tooling.
- Implement schemas, configuration loading, logging, and CLI skeleton.
- Add CI.

**Exit:** Fresh clone passes empty test suites, linting, and frontend build.

## Milestone B - BigQuery discovery

- Implement SQL templates and dry-run guard.
- Build extraction and aggregation.
- Produce sample Parquet outputs.

**Exit:** Pilot discovery report passes Phase 3 acceptance criteria.

## Milestone C - Enrichment and classification

- Implement GraphQL batching, cache, checkpoints, and rate handling.
- Enrich repositories.
- Implement deterministic taxonomy classifier.
- Complete manual validation workflow.

**Exit:** Classification precision gate passes.

## Milestone D - Contributors and locations

- Extract contributor activity.
- Enrich public profile locations.
- Implement offline normalization and validation.

**Exit:** Location precision gates pass and public privacy tests pass.

## Milestone E - Scoring and rankings

- Implement repository, contributor, opportunity, and confidence scores.
- Run stability and bias analyses.

**Exit:** Rankings are reproducible and validation report is complete.

## Milestone F - Premium UI

- Implement static data builder.
- Build routes, map, ranking rail, detail, compare, methodology, and recommendations.
- Complete responsive and accessibility work.

**Exit:** UI acceptance and E2E tests pass.

## Milestone G - Deploy and package

- Deploy to Cloudflare Pages.
- Freeze dataset version.
- Write research report.
- Record demo.

**Exit:** Public URL works, $0 constraint is met, and no private data is exposed.

---

# 30. Definition of Done

The project is done only when:

- The full Cloud/DevOps pilot pipeline runs from documented commands.
- Query and API usage are logged.
- Qualified repositories and contributors meet minimum sample requirements.
- Classification and location validation thresholds pass or failures are transparently reported.
- Opportunity and confidence scores are separate and reproducible.
- Public data contains no usernames or raw profile data.
- The dashboard is responsive, accessible, fast, and visually polished.
- It is deployed on a free Cloudflare Pages URL.
- No credit card or billing-enabled service was used.
- The research report contains real findings, not predetermined claims.
- The README contains setup, pipeline, methodology, demo, limitations, and live-site links.

---

# 31. Verified Platform Constraints and References

Verified on **August 1, 2026**. Recheck before implementation because platform limits may change.

1. GitHub REST API rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
2. GitHub GraphQL rate limits: https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api
3. BigQuery Sandbox: https://docs.cloud.google.com/bigquery/docs/sandbox
4. GH Archive: https://www.gharchive.org/
5. GitHub Actions billing and public repositories: https://docs.github.com/en/actions/concepts/billing-and-usage
6. Cloudflare Pages limits: https://developers.cloudflare.com/pages/platform/limits/
7. Cloudflare Pages pricing/static requests: https://developers.cloudflare.com/pages/functions/pricing/
8. MapLibre GL JS: https://maplibre.org/maplibre-gl-js/docs

---

# 32. First Command to the Coding Agent

Use this exact instruction after attaching this document:

> Build CodeTalent Atlas according to the attached specification. Start with Milestone A only. Create the repository foundation, configuration contracts, Pydantic schemas, Typer CLI skeleton, logging, test setup, Vite React frontend shell, and CI. Do not begin BigQuery extraction yet. Run all available tests and provide a concise summary of files created, commands run, and any specification conflicts.

