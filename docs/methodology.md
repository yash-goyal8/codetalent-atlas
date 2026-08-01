# CodeTalent Atlas — Methodology

**Status:** Skeleton written in Milestone A. Structure and formulas are locked from the build spec; sections marked *[awaits data — Milestone X]* are completed only when the corresponding pipeline stage has actually run. This document contains no results and no invented numbers.

**Source of truth:** [`docs/CODETALENT_ATLAS_BUILD_SPEC.md`](CODETALENT_ATLAS_BUILD_SPEC.md), sections 5, 12–17.

---

## 1. Data sources

All sources are free and public; no scraping, no paid services.

| Source | Role | Constraints |
|---|---|---|
| GH Archive public BigQuery dataset | Discovery of public GitHub events (PushEvent, PullRequestEvent, PullRequestReviewEvent, IssuesEvent, IssueCommentEvent, ReleaseEvent) | BigQuery Sandbox only, no billing; pilot query budget ≤ 250 GiB processed; 1 TiB monthly free ceiling preserved |
| GitHub GraphQL API | Repository metadata and public user profile enrichment | Authenticated free allowance (~5,000 points/hour); low concurrency, caching, checkpoints |
| GitHub REST API | Only fields GraphQL cannot provide (lightweight content checks for a small shortlist) | Authenticated free allowance (~5,000 requests/hour) |
| Offline gazetteers (`pycountry`, `country_converter`, `geonamescache`), curated alias/override tables, Natural Earth geometries | Location normalization and public visualization | Fully offline; no live geocoding API |

*Actual query bytes, API point usage, and fetch success rates: [awaits data — Milestones B–D; recorded in `reports/query_usage.csv` and `reports/enrichment_usage.csv`].*

## 2. Data funnel

Planned funnel stages (counts to be filled from real runs):

1. Raw events in window (2026-05-01 to 2026-07-31) → *[awaits data — Milestone B]*
2. Events after bot and automation removal → *[awaits data — Milestone B]*
3. Candidate repositories discovered → *[awaits data — Milestone B]*
4. Repositories passing activity filters → *[awaits data — Milestone B]*
5. Repositories passing Cloud/DevOps relevance and quality filters → *[awaits data — Milestone C]*
6. Unique non-bot contributors in qualified repositories → *[awaits data — Milestone D]*
7. Contributors with usable country-level locations → *[awaits data — Milestone D]*
8. Countries and cities meeting minimum sample rules → *[awaits data — Milestone E]*

Event weights used in weighted activity (fixed by spec):

| Event | Weight |
|---|---|
| Merged pull request | 5 |
| Pull-request review | 4 |
| Pull request opened | 3 |
| Release | 3 |
| Push event | 2 |
| Issue opened or commented | 1 |

## 3. Repository inclusion and exclusion

A repository qualifies only if it is:

- Public; not a fork; not archived or disabled
- Active within the selected window
- Associated with at least 5 unique human contributors
- Associated with at least 20 meaningful events
- Associated with at least 3 pull requests or reviews
- Active in at least 2 months during the three-month pilot
- Clearly related to at least one Cloud/DevOps subdomain
- Covered by a recognized open-source license

Excluded: bots and automation accounts; dotfiles; tutorial-only projects; student assignments; interview-preparation repositories; awesome lists; documentation-only repositories; mirrors and generated copies; abandoned repositories; repositories where one actor accounts for more than 90% of meaningful activity; repositories with suspicious burst patterns; repositories unrelated to production engineering.

Classification uses transparent weighted rules (topics, description/name terms, primary language, domain-file signals, negative terms). No LLM, paid or local, is used for classification.

*Classifier precision and false-inclusion rate from the 150-repository manual sample: [awaits data — Milestone C; recorded in `reports/classification_validation.csv`].*

## 4. Location normalization and confidence

Free-form public locations are normalized offline in a fixed order: placeholder removal → unicode/whitespace cleanup → manual override → exact alias → ISO country code or country name → city-country pair → unique global city → region+country → ambiguity detection → unresolved.

Confidence labels: **high** (explicit unambiguous country; exact curated city-country pair; documented manual override), **medium** (unique city with one dominant global match; state/region plus country), **low** (ambiguous city resolved heuristically; broad region only), **unusable** (jokes, virtual locations, conflicts, unresolved).

Aggregation eligibility: country rankings use high and medium country matches; city rankings use high-confidence city matches only; low-confidence matches appear only in coverage diagnostics.

*Country and city precision from the 500-string manual sample: [awaits data — Milestone D; recorded in `reports/location_validation.csv`].*

## 5. Score formulas

All weights live in `config/scoring.yaml`; no weight exists only in source code. All scores are on a 0–100 scale, deterministic, and use robust scaling (percentile ranks, `log1p`, winsorization at the 99th percentile, bounded subscores).

### 5.1 Repository quality score

```text
Repository Quality =
  30% Recent Activity
+ 25% Contributor Diversity
+ 20% Collaboration Quality
+ 15% Technical Relevance
+ 10% Repository Maturity
```

### 5.2 Contributor expert score (per domain)

```text
Expert Score =
  35% Domain Activity
+ 25% Contribution Quality
+ 20% Repository Quality Exposure
+ 10% Continuity
+ 10% Collaboration
```

Bias safeguards: followers are never used; one repository contributes at most 40% of a contributor's score; raw push volume is capped; at least two meaningful active days are required; one-repository contributors are marked separately; raw and weighted counts are both kept. The "Contribution Quality" component is contribution-quality *evidence* from event types — it is not a claim about intrinsic code quality.

### 5.3 Geographic opportunity score (per domain and geography)

```text
Opportunity Score =
  35% Expert Supply
+ 30% Expert Quality
+ 15% Collaboration Depth
+ 10% Momentum
+ 10% Ecosystem Breadth
```

For the three-month pilot, momentum is labeled provisional and uses month-over-month direction only.

### 5.4 Confidence score

```text
Confidence Score =
  35% Located Profile Coverage
+ 25% Location Certainty
+ 20% Sample Size Adequacy
+ 10% Repository Diversity
+ 10% Organization Diversity
```

## 6. Confidence separation principle

Confidence is computed, stored, and displayed **separately** from opportunity. The two are never merged into one opaque number. A high opportunity score with low confidence must not be labeled a priority recommendation. Every published ranking carries both scores, and every recommendation states its confidence and its main coverage or concentration risk.

## 7. Minimum sample rules

A geography is ranked only if it meets all thresholds; otherwise it is labeled `insufficient_data` and receives no normal rank.

| Level | Located contributors | Qualified repositories | Organizations |
|---|---|---|---|
| Country | ≥ 30 | ≥ 10 | ≥ 5 |
| City | ≥ 25 (high-confidence locations only) | ≥ 8 | ≥ 4 |

## 8. Recommendation tiers

Configuration-driven; thresholds fixed by spec:

```text
Priority:            Opportunity >= 75 and Confidence >= 70
Promising:           Opportunity >= 60 and Confidence >= 60
Monitor:             Opportunity >= 45 or Confidence between 45 and 59
Insufficient data:   Sample rule failed or Confidence < 45
```

Concentration safeguards: any single repository's contribution to a geography's weighted supply is capped; any organization contributing more than 20% of a location's weighted activity is flagged; raw and weighted counts are both shown; a concentration-risk indicator accompanies each ranking.

## 9. Validation and sensitivity

*Entire section awaits data — Milestone E.* Planned content: data-quality checks (nulls, duplicates, referential integrity, schema compliance, bounds), classification and location precision results, ranking-stability tests (drop top 1% of repositories by activity; drop the largest organization per country; vary score weights ±20%; compare three- and twelve-month windows; compare raw and weighted contributor counts), and coverage-bias measurements (see [`docs/bias_limitations.md`](bias_limitations.md)).

## 10. Limitations

Representation limitations and coverage-bias findings are maintained in [`docs/bias_limitations.md`](bias_limitations.md) and surfaced in the product itself, not only in the repository.
