# CodeTalent Atlas — Privacy and Ethics Policy

**Status:** Phase 0 deliverable. Binding on every subsequent milestone.
**Source of truth:** [`docs/CODETALENT_ATLAS_BUILD_SPEC.md`](CODETALENT_ATLAS_BUILD_SPEC.md), sections 9.5, 15, 26, and 27.

---

## 1. Aggregate-only publication

The public website and every public data asset expose **aggregates only**: country- and city-level scores, counts, coverage rates, and subdomain summaries. The product never ranks, lists, profiles, or displays an individual developer, publicly or in any exported artifact. This is a product decision, not merely a compliance one: the question the product answers is about locations, and individual-level output would add risk without adding evidence.

## 2. Fields deliberately not collected

User profile enrichment fetches only: login, account type, public location string, account creation date, and follower count (the last for descriptive coverage analysis only — never used in the expert score).

The pipeline deliberately does **not** collect or store, even though the GitHub API exposes them publicly:

- Email addresses
- Names
- Employer / company fields
- Websites and blog URLs

These fields are unnecessary for geographic aggregation. They may not be added unless a later research requirement is explicitly approved and this policy is revised first.

## 3. Individual-level data stays local

The mapping `actor_login -> raw location / normalized location` is required internally to build aggregates. It:

- lives only under `data/` directories that are gitignored (`data/raw`, `data/cache`, and full user-level processed files);
- is never committed, never published, and never included in `data/public` or `web/public/data`;
- is never exposed through any public JSON, chart, tooltip, or download.

Only aggregate outputs derived from it are published.

## 4. Prohibited public content

Per spec section 27, the following are prohibited in `web/public/data` and `data/public`:

- `actor_login`
- `user_login`
- GitHub profile URL
- Raw location string
- Email addresses
- Names
- API tokens

Allowed public content: aggregate counts, country/city names, scores, repository counts, organization counts, and subdomain summaries.

## 5. Automated enforcement

A privacy scanner (implemented in Milestone A so it guards every later milestone) recursively scans `web/public/data` and `data/public` for the prohibited fields and patterns above. It runs in CI and in the deployment pipeline. **A violation blocks the build and deployment.** A recommendation that cannot pass the scanner does not ship.

## 6. Collection ethics

- **No scraping.** Data comes only from the GH Archive public BigQuery dataset and the official GitHub API. GitHub HTML pages are never scraped.
- **Rate-limit respect is an ethics matter, not just an engineering one.** Free public APIs are a shared resource. The client reads rate-limit headers and GraphQL `rateLimit` data, pauses before budgets are exhausted, obeys `Retry-After`, backs off exponentially with jitter, and holds concurrency to a conservative default of 2. Sustained 403/429 behavior is treated as a defect.
- **Caching over refetching.** Every external response is cached locally; completed records are never refetched before their cache TTL. This minimizes load on public infrastructure and keeps runs reproducible.
- **No secrets in the repository.** Tokens live in environment variables locally and repository secrets in CI, are scoped to public-read only, and are never exposed to the frontend.

## 7. Data-subject considerations

The pipeline processes data that GitHub users have chosen to make public: public events and public profile fields. That choice does not eliminate responsibility:

- **Purpose limitation.** Public data is used solely to produce location-level aggregates for sourcing analysis, not to profile, contact, or evaluate any individual.
- **No re-identification.** Aggregation thresholds (minimum located contributors, repositories, and organizations per published location) reduce the risk that a published figure describes an identifiable person. Locations below threshold are labeled `insufficient_data` rather than published with small samples.
- **Self-reported fields are treated as unreliable and personal.** Location strings may be missing, stale, humorous, or ambiguous; they are normalized with explicit confidence labels and never republished in raw form.
- **No inference of private facts.** The pipeline does not infer contact information, employment, availability, or willingness to work from public activity, and the product states this limitation openly (see [`docs/bias_limitations.md`](bias_limitations.md)).
- **Deletion respected by refresh.** Profiles that become unavailable (deleted or made private) are recorded as `not_found` and drop out of future aggregates on refresh rather than being preserved from stale caches beyond their TTL.

## 8. Scope of this policy

This policy binds all milestones (A through G), all contributors to this repository, and all automation acting on it. Any change requires an explicit entry in [`docs/decisions.md`](decisions.md) before implementation.
