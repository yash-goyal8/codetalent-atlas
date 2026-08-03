# Feasibility Report (spec Phase 1)

**Status:** BigQuery-side feasibility measured during Milestone B (2026-08-01/02). GraphQL-side fields are produced by Milestones C–D and are explicitly **pending** — no GitHub API call has been made yet.

## Measured (BigQuery discovery, Cloud/DevOps pilot window 2026-05-01 → 2026-07-31)

| Metric | Value |
|---|---|
| BigQuery bytes processed (phase total, all executed queries) | 372,798,194,029 bytes (347.19 GiB; 33.9% of the 1 TiB monthly free tier; $0) |
| Query runtime | 22–27 s per month materialization; 1–18 s per downstream stage (per-query rows in `query_usage.csv`) |
| Candidate repository count | 309,653 discovered; 19,456 pass activity filters |
| Unique actor count | 204,202 unique human contributors across activity-passed repositories |
| Bot share | 15.1% of counted events (38,598 distinct bot actors), flagged not dropped |

**Verdict for the BigQuery leg: PROCEED.** Free-tier quota comfortably accommodates the pilot even including the one-time schema-drift rework (decisions B-03/B-05); the funnel exceeds both Phase 3 targets.

Material caveat for planning: the 2026 GH Archive payload no longer carries push commit counts, and PR merge detection required era-robust extraction (decisions B-03/B-04). The expanded twelve-month run must budget for both payload eras.

## Measured (GitHub GraphQL, Milestones C–D, 2026-08-03)

| Metric | Value |
|---|---|
| GraphQL requests / points used | 1,223 requests, 1,212 points total (802 repo batches + 421 user batches) — ~24% of ONE hourly window across the whole pilot |
| Repository enrichment success | 19,223 / 19,456 (98.8%; 233 deleted/renamed quarantined) — gate ≥95% PASS |
| Profile fetch success rate | 10,412 / 10,500 (99.2%; 88 deleted accounts) — gate ≥90% PASS |
| Non-empty location rate | 51.9% of successful profiles |
| Country-normalizable rate | **46.6%** (high+medium confidence) — **≥40% target PASS** |
| City-normalizable rate (high confidence) | 14.5% |

**Final verdict: PROCEED.** Every feasibility threshold is met at $0. The architecture scales to the twelve-month expanded run within free quotas (BigQuery at ~34% of one monthly free tier including the one-time schema-drift rework; GraphQL usage is negligible).
