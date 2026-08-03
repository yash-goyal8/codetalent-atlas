# CodeTalent Atlas — Research Report

**Dataset:** 2026.08.03-pilot.1 (frozen) · **Methodology:** v1.0.0 · **Domain:** Cloud and DevOps · **Window:** 2026-05-01 → 2026-07-31 · **Total build/processing cost: $0**

---

## 1. Executive summary

CodeTalent Atlas answers a sourcing question with public, reproducible data: **where should Scale investigate building sourcing pipelines for expert Cloud/DevOps contributors?** From three months of public GitHub activity (GH Archive via BigQuery Sandbox), the pipeline discovered 309,653 candidate repositories, qualified 639 as genuinely collaborative Cloud/DevOps projects, scored 5,636 observable expert contributors, and ranked 23 countries (and 5 cities) on separate **opportunity** and **confidence** scales.

**Recommended sourcing pilots: Germany (opportunity 64.1 / confidence 70.6), India (60.5 / 76.8), and China (60.2 / 68.1)** — the three "promising"-tier locations where both evidence strength and data trustworthiness clear the configured bars. The United States tops raw opportunity (67.3) but carries the weakest located-profile confidence (58.1) among the leaders and is deliberately not a top recommendation until coverage improves. No location reaches the "priority" tier (opportunity ≥75 AND confidence ≥70) in a three-month window — reported as-is rather than tuned away.

Most important limitation: only 46.6% of observable contributors expose a usable country; every ranking therefore carries an explicit confidence score, and momentum is provisional at pilot length.

## 2. Business question

Primary question (verbatim from the product spec): *"Where should Scale investigate and build sourcing pipelines for expert contributors across high-value coding domains?"*

The narrower question the data can defensibly answer: *"Among observable, active contributors to qualified public repositories, which locations show the strongest combination of expert supply, quality, collaboration depth, momentum, and ecosystem breadth for a selected coding domain?"* The distinction matters: this measures the observable public slice, not the total labor market (section 12).

## 3. Why public open-source activity is directionally useful

Expert Cloud/DevOps engineers disproportionately work in public: the domain's core tools (Kubernetes, Terraform, Prometheus, Argo, OpenTelemetry) are developed in the open, and meaningful participation — merged PRs, code reviews — is costly to fake and visible in the event stream. Event *types* carry signal that raw counts do not: a merged pull request or a submitted review implies peer acceptance in a way a push never can. The pipeline weights accordingly and treats everything as *evidence of contribution*, never as a claim about intrinsic developer quality.

## 4. Data sources

| Source | Use | Cost control |
|---|---|---|
| GH Archive monthly tables (BigQuery public dataset) | Event discovery, 3 pilot months | BigQuery Sandbox (no billing attached); every query dry-run first, byte-capped, cumulative ledger; total 350.4 GiB = 34.2% of one free monthly TiB |
| GitHub GraphQL API | Repository metadata (19,223 repos) + public profiles (10,500 contributors) | 1,223 requests / 1,212 points total; cached, checkpointed, rate-limit-aware |
| Offline gazetteers (pycountry, country_converter, geonamescache) | Location normalization | No geocoding API, fully offline |

A material finding for anyone using GH Archive in 2026: the payload schema changed — merged PRs now emit `action='merged'` (the classic `pull_request.merged` flag is gone) and push commit counts no longer exist in payloads at all. Both were caught by validation, fixed era-robustly, and documented (decisions B-03/B-04).

## 5. Repository taxonomy

Eight subdomains (IaC, containers/orchestration, CI/CD & developer tooling, observability, configuration management, service mesh/networking, cloud platforms/SDKs, SRE), classified by deterministic weighted rules over topics, name/description terms, and content signals, with hard exclusion overrides (forks, archived, unrecognized license, docs-only, tutorials, student projects, >90% single-actor dominance). No LLM anywhere in the pipeline.

## 6. Data funnel

| Stage | Count |
|---|---:|
| Repositories in activity summary (≥2 human contributors or name signal) | 1,052,819 |
| Discovered Cloud/DevOps candidates | 309,653 |
| Passing activity filters (5 contributors / 20 events / 3 PRs-or-reviews / 2 months) | 19,456 |
| Enriched with GraphQL metadata | 19,223 (98.8%) |
| **Qualified Cloud/DevOps repositories** | **639** (+790 borderline queued for review) |
| **Scored expert contributors** | **5,636** across 12,198 owner organizations |

The 639 qualified count sits below the spec's 1,000+ aspiration; the 790-repo borderline queue (13/50 sampled were judged relevant) is the documented path to close the gap in the next iteration.

## 7. Scoring methodology

Four layers, all weights in `config/scoring.yaml`, none in code: repository quality (30/25/20/15/10: recent activity, contributor diversity, collaboration quality, technical relevance, maturity); contributor expert score (35/25/20/10/10: domain activity, contribution-quality evidence, repository-quality exposure, continuity, collaboration) with bias safeguards (no followers, 40% single-repo cap, capped push volume, ≥2 active days); geography opportunity (35/30/15/10/10: supply, quality, collaboration depth, momentum, breadth) and **separate** confidence (35/25/20/10/10: located coverage, location certainty, sample adequacy, repository and organization diversity). Robust scaling throughout (winsorization at p99, log1p, percentile ranks); expert quality uses weighted medians, never means. Minimum samples gate every ranking (country: 30 located contributors / 10 repos / 5 orgs).

## 8. Validation

- **Classification:** 150-repo stratified review, documented rubric — 92% precision, 4% false inclusion (gates: ≥90%, <10%). Labels committed.
- **Locations:** 500-string stratified review — 100% country and 100% city precision on high-confidence labels (gates: ≥95%, ≥90%). Review-driven fixes landed before freezing (bare-state-name and state-vs-ISO-anchor traps).
- **Data quality:** 11 automated checks green (keys, bounds, dates, referential integrity, merged≤closed).
- **Reviewer caveat:** both manual reviews were performed by the build agent applying committed rubrics, not an independent human; all samples and labels are committed for re-audit.

## 9. Findings

1. **The observable Cloud/DevOps expert pool is globally distributed but US/EU/Asia-anchored.** Top rankable countries: US, DE, IN, CN, GB, CA, FR, AU, PL, ES, IE, IL.
2. **Opportunity and confidence genuinely diverge.** The US leads opportunity (67.3) with the weakest leader confidence (58.1 — US contributors disproportionately omit locations); India shows the *highest* confidence (76.8) on solid opportunity (60.5).
3. **Subdomain textures differ by country:** US strength concentrates in cloud platforms/SDKs; Germany and India lead with containers/orchestration; Britain's top subdomain is observability; India shows unusual IaC depth.
4. **Collaboration breadth is meaningful at the top:** 28–29% of US and India experts contribute to multiple qualified repositories (multi-repo share), vs 17% for Germany — different sourcing textures (broad ecosystem participants vs project-anchored specialists).
5. **No priority-tier location exists at pilot scale** — three months of data cannot clear opportunity ≥75 with confidence ≥70. The twelve-month expansion is the test of whether that tier is reachable.

## 10. Recommended sourcing pilots

Per the spec template (evidence → confidence → risk → next step):

1. **Investigate Germany for Containers/Orchestration and Cloud Platform contributors.** Evidence: #2 overall; 284 observable experts, 133 qualified repos, 96 organizations; balanced components. Confidence: 70.6 (best-in-class coverage among top-3). Risk: lowest multi-repo share among leaders (17%) — experts are project-anchored; source through flagship projects. Next step: small sourcing pilot; validate response and qualification rates.
2. **Investigate India for Containers/Orchestration and IaC contributors.** Evidence: #3; 245 experts, 152 qualified repos (more than Germany), 95 orgs; highest confidence on the board (76.8); 29% multi-repo share. Risk: expert-quality component trails supply — screen depth explicitly. Next step: pilot targeting IaC + containers contributors.
3. **Investigate China for Cloud Platform/SDK and Observability contributors.** Evidence: #4; 142 experts, 87 repos, 57 orgs; strong observability ecosystem presence. Risk: smallest observable pool of the three; platform-access and language considerations for outreach. Next step: scoped pilot via the observability project ecosystem.

**Conditional fourth: the United States** — the largest pool (684 experts, 301 repos, 180 orgs) but confidence 58.1; recommended only alongside a location-coverage improvement effort, not as a standalone pilot.

## 11. Sensitivity analysis

Top-10 country rankings under stress (detail: `reports/sensitivity_rankings.csv`): opportunity supply-weight ±20% (renormalized), top-1%-of-repositories removal, and largest-organization removal (microsoft) produce at most **one-position swap between adjacent near-ties** (IN↔CN). No recommendation depends on a fragile ranking.

## 12. Biases and limitations

GitHub activity ≠ the developer workforce; public behavior varies by region, employer, and culture. Self-reported locations are missing for half the pool (46.6% usable coverage) and skew by geography. Event counts measure contribution evidence, not engineering quality. Open-source presence does not imply availability or willingness to contract. Push commit counts are structurally absent from the 2026 payload era. Momentum is provisional at three months. Coverage, confidence, and concentration risks are displayed per-location in the product rather than confined to this appendix. Full treatment: `docs/bias_limitations.md`.

## 13. Next steps

1. Expand to the latest twelve complete months (momentum becomes real; priority tier becomes reachable; both payload eras handled by the era-robust extraction).
2. Review the 790-repo borderline queue (13/50 sampled were relevant) to close the gap to 1,000+ qualified repositories.
3. Add the four expansion domains (backend/distributed systems, C/C++ systems, GPU computing, cybersecurity) — the pipeline is domain-parameterized end to end.
4. Independent human re-audit of the two rubric-based validation samples.
5. Monthly refresh via the existing manual-dispatch workflow, preserving dataset versions for rank-change analysis.
