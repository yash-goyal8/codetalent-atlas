# CodeTalent Atlas — Data Dictionary

Field-level documentation for the eight core data schemas defined in build-spec section 9. These schemas are implemented as Pydantic models in `src/codetalent/schemas.py` with matching Parquet schemas. Types below are the logical types from the spec; nullability is explicit — every field not marked nullable is required.

Datasets 1–7 are **internal and local only**. Only dataset 8 (geographic ranking) feeds public aggregates, and even then only scanner-approved fields are published.

---

## 1. Repository activity summary

One row per candidate repository, aggregated from GH Archive events over the pilot window. Produced by Milestone B.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `repo_name` | string | no | Full repository name, `owner/name`; primary key |
| `owner_login` | string | no | Repository owner login (user or organization) |
| `repo_short_name` | string | no | Repository name without the owner prefix |
| `unique_human_contributors` | int | no | Distinct non-bot actors with meaningful events in the window |
| `active_days` | int | no | Distinct calendar days with at least one meaningful event |
| `active_months` | int | no | Distinct calendar months with at least one meaningful event |
| `push_events` | int | no | PushEvent count in the window |
| `push_commit_count` | int | no | Total commits carried by push events |
| `pull_requests_opened` | int | no | Pull requests opened in the window |
| `pull_requests_closed` | int | no | Pull requests closed in the window |
| `merged_pull_requests` | int | no | Pull requests merged in the window |
| `reviews_submitted` | int | no | Pull-request reviews submitted |
| `issues_opened` | int | no | Issues opened |
| `issue_comments` | int | no | Issue comments posted |
| `releases` | int | no | Releases published |
| `weighted_activity_score` | float | no | Event counts combined with spec event weights (merged PR 5, review 4, PR opened 3, release 3, push 2, issue/comment 1) |
| `first_seen` | date | no | Date of the first observed event in the window |
| `last_seen` | date | no | Date of the last observed event in the window |
| `automation_event_share` | float | no | Share of events attributed to bot/automation accounts before filtering |
| `single_actor_event_share` | float | no | Share of meaningful events from the single most active actor (dominance signal; excluded above 0.90) |
| `discovery_status` | string | no | Pipeline status of this candidate (e.g. discovered, activity-filtered) |
| `exclusion_reason` | string | yes | Why the repository was excluded, if it was; null otherwise |

## 2. Repository metadata

One row per enriched repository, fetched via GitHub GraphQL (plus limited REST content checks for a small shortlist). Produced by Milestone C.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `repo_name` | string | no | Full repository name; primary key, joins to activity summary |
| `description` | string | yes | Repository description as set by the owner |
| `is_fork` | bool | no | Whether the repository is a fork (forks are excluded) |
| `is_archived` | bool | no | Whether the repository is archived (excluded) |
| `is_disabled` | bool | no | Whether the repository is disabled (excluded) |
| `primary_language` | string | yes | Primary language reported by GitHub |
| `topics` | list[string] | no | Repository topics (first 20); empty list if none |
| `stargazer_count` | int | no | Star count (descriptive only; never a proxy for expertise by itself) |
| `fork_count` | int | no | Fork count |
| `license_spdx_id` | string | yes | SPDX identifier of the license; null if unrecognized or absent |
| `pushed_at` | datetime | yes | Timestamp of the last push known to GitHub |
| `updated_at` | datetime | yes | Timestamp of the last repository update |
| `release_count` | int | no | Total releases |
| `issue_count` | int | no | Total issues |
| `pull_request_count` | int | no | Total pull requests |
| `has_readme` | bool | yes | README exists; null when the lightweight content check was not run |
| `has_contributing` | bool | yes | CONTRIBUTING file exists; null when not checked |
| `has_code_of_conduct` | bool | yes | CODE_OF_CONDUCT exists; null when not checked |
| `has_ci` | bool | yes | CI configuration present; null when not checked |
| `has_tests_signal` | bool | yes | Test directory or test files detected; null when not checked |
| `graphql_fetched_at` | datetime | no | When this record was fetched (drives cache TTL) |

## 3. Repository classification

One row per classified repository per domain. Produced by the deterministic taxonomy classifier in Milestone C.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `repo_name` | string | no | Full repository name |
| `domain_id` | string | no | Domain being classified (pilot: `cloud_devops`) |
| `subdomains` | list[string] | no | Matched subdomain ids; a repository may carry multiple labels |
| `classification_score` | float | no | Weighted rule score supporting the decision |
| `classification_status` | enum | no | One of `accepted`, `rejected`, `borderline` |
| `evidence_topics` | list[string] | no | Topics that matched positive taxonomy entries |
| `evidence_terms` | list[string] | no | Description/name terms that matched |
| `evidence_files` | list[string] | no | Domain-signal files that matched (e.g. `Dockerfile`, `*.tf`) |
| `negative_evidence` | list[string] | no | Matched negative terms/patterns counting against inclusion |
| `manual_label` | string | yes | Human label from the 150-repository validation sample; null if not manually reviewed |
| `manual_notes` | string | yes | Reviewer notes for the manual label |

## 4. Contributor activity

One row per (contributor, repository, domain), aggregated from GH Archive events in qualified repositories. Produced by Milestone D. Internal only.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `actor_login` | string | no | GitHub login of the contributor (never published) |
| `repo_name` | string | no | Qualified repository the activity occurred in |
| `domain_id` | string | no | Domain of the repository |
| `subdomains` | list[string] | no | Subdomain labels of the repository |
| `push_events` | int | no | Push events by this actor in this repository |
| `pull_requests_opened` | int | no | Pull requests opened by this actor |
| `merged_pull_requests_authored` | int | no | Authored pull requests that were merged |
| `reviews_submitted` | int | no | Reviews submitted by this actor |
| `issues_opened` | int | no | Issues opened |
| `issue_comments` | int | no | Issue comments posted |
| `active_days` | int | no | Distinct days with meaningful activity |
| `active_months` | int | no | Distinct months with meaningful activity |
| `first_seen` | date | no | First observed activity date in the window |
| `last_seen` | date | no | Last observed activity date in the window |
| `raw_contribution_points` | float | no | Event counts combined with spec event weights, before capping or normalization |

## 5. Public user profile enrichment

One row per fetched contributor profile. Produced by Milestone D. Internal only; gitignored. Public email, employer, website, and name are deliberately **not collected** (see `docs/privacy_ethics.md`).

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `actor_login` | string | no | GitHub login; primary key (never published) |
| `account_type` | enum | no | One of `user`, `bot`, `organization`, `unknown` |
| `public_location_raw` | string | yes | Free-form public location string exactly as set by the user; null if unset |
| `created_at` | datetime | yes | Account creation date |
| `followers_count` | int | yes | Follower count — descriptive coverage analysis only, never used in the expert score |
| `profile_fetched_at` | datetime | no | When this profile was fetched (drives cache TTL) |
| `fetch_status` | enum | no | One of `success`, `not_found`, `rate_limited`, `error` |

## 6. Normalized location

One row per contributor with a processed location. Produced by offline normalization in Milestone D. Internal only; gitignored; the `actor_login -> location` mapping is never published.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `actor_login` | string | no | GitHub login (never published) |
| `raw_location` | string | yes | Input location string; null if the profile had none |
| `normalized_country_code` | string | yes | ISO 3166-1 alpha-2 code; null if unresolved |
| `normalized_country_name` | string | yes | Resolved country name |
| `normalized_city` | string | yes | Resolved city; null when only country/region resolved |
| `latitude` | float | yes | City centroid latitude from the offline gazetteer |
| `longitude` | float | yes | City centroid longitude |
| `location_level` | enum | no | One of `city`, `country`, `region`, `unknown` |
| `location_confidence` | enum | no | One of `high`, `medium`, `low`, `unusable` (see methodology for rules) |
| `normalization_method` | enum | no | One of `exact_alias`, `parsed_country`, `unique_city`, `city_country_pair`, `manual_override`, `unresolved` |
| `ambiguity_reason` | string | yes | Why the string was ambiguous or unresolved, when applicable |

## 7. Contributor score

One row per (contributor, domain). Produced by Milestone E. Internal only; individuals are never ranked publicly.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `actor_login` | string | no | GitHub login (never published) |
| `domain_id` | string | no | Domain the score applies to |
| `expert_score` | float | no | 0–100 composite: 35% domain activity + 25% contribution quality + 20% repository quality exposure + 10% continuity + 10% collaboration |
| `domain_activity_score` | float | no | Component: domain-weighted event points, qualified repo count, subdomain breadth |
| `contribution_quality_score` | float | no | Component: event-type evidence (merged PRs, reviews, capped pushes); evidence, not intrinsic quality |
| `repository_quality_exposure_score` | float | no | Component: capped weighted average of quality scores of repositories the contributor was active in |
| `continuity_score` | float | no | Component: active months, repeat activity, recency |
| `collaboration_score` | float | no | Component: reviews, PR participation, multi-repository and multi-organization activity |
| `qualified_repo_count` | int | no | Qualified repositories the contributor was active in |
| `active_months` | int | no | Distinct active months in the window |
| `country_code` | string | yes | Normalized country; null if unresolved or unusable |
| `city` | string | yes | Normalized city; null unless a high-confidence city resolved |
| `location_confidence` | string | no | Confidence label carried from normalization |

## 8. Geographic ranking

One row per (geography, domain). Produced by Milestone E; the only dataset whose aggregates feed public assets.

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `geo_level` | enum | no | One of `country`, `city` |
| `geo_id` | string | no | Stable geography identifier (country code, or a city slug) |
| `country_code` | string | no | ISO country code of the geography |
| `city` | string | yes | City name; null for country rows |
| `domain_id` | string | no | Domain the ranking applies to |
| `opportunity_score` | float | no | 0–100 composite: 35% expert supply + 30% expert quality + 15% collaboration depth + 10% momentum + 10% ecosystem breadth |
| `confidence_score` | float | no | 0–100 composite, kept separate from opportunity: 35% located profile coverage + 25% location certainty + 20% sample size adequacy + 10% repository diversity + 10% organization diversity |
| `expert_supply_score` | float | no | Component: weighted unique contributor count, log-scaled, elite-capped |
| `expert_quality_score` | float | no | Component: weighted median expert score and top-quartile share |
| `collaboration_depth_score` | float | no | Component: multi-repo expert share, review participation, recurring contributors |
| `momentum_score` | float | no | Component: activity trend; provisional (month-over-month only) in the three-month pilot |
| `ecosystem_breadth_score` | float | no | Component: repository count, organization count, subdomain breadth, concentration penalty |
| `observable_expert_count` | int | no | Raw count of located qualified contributors |
| `weighted_expert_count` | float | no | Expert-score-weighted contributor count (shown alongside raw, never instead of it) |
| `qualified_repo_count` | int | no | Qualified repositories attributed to the geography |
| `organization_count` | int | no | Distinct organizations attributed to the geography |
| `multi_repo_expert_share` | float | no | Share of experts active in more than one qualified repository |
| `located_profile_coverage` | float | no | Share of the geography's contributors with usable locations (confidence input) |
| `high_confidence_location_share` | float | no | Share of located profiles at high confidence |
| `top_subdomains` | list[string] | no | Strongest subdomains for this geography |
| `rank` | int | no | Rank within (geo_level, domain) among geographies meeting sample rules |
| `recommendation_tier` | enum | no | One of `priority`, `promising`, `monitor`, `insufficient_data` per configured thresholds |

---

## Report artifacts in this directory

| File | Filled by | Contents |
|---|---|---|
| `query_usage.csv` | Milestone B onward | One row per BigQuery query: estimated and actual bytes, runtime, status (header committed in Milestone A) |
| `enrichment_usage.csv` | Milestones C–D | One row per GitHub API batch: cost, remaining budget, retries, cache hits (header committed in Milestone A) |
| `feasibility.md` | Milestone B | Phase 1 feasibility findings: bytes, counts, bot share, location rates, proceed/adjust recommendation |
| `discovery_validation.md` | Milestone B | Phase 3 discovery validation: funnel counts, bot-removal audit, sample inspections |
| `classification_validation.csv` | Milestone C | Manual labels for the 150-repository stratified sample; column set confirmed with the classifier |
| `location_validation.csv` | Milestone D | Manual review of 500 stratified location strings; column set confirmed with the normalizer |
| `ranking_validation.md` | Milestone E | Ranking stability, sensitivity tests, and coverage-bias measurements |
