# CodeTalent Atlas — Research Report

**Status:** Structure only, fixed by build-spec section 23. The spec forbids pre-written conclusions: findings, recommendations, and sensitivity results are generated only after the validated dataset exists (Milestone E complete; report written in Milestone G). Until then, every section below carries a description of its eventual content and nothing else. No numbers in this document are real until the dataset version they cite is frozen.

---

## 1. Executive summary

Will state, in under a page, the core question, the method in one paragraph, the three or more recommended sourcing pilots with opportunity and confidence scores, and the single most important limitation. Written last.

## 2. Business question

Will state the core question — "Where should Scale investigate and build sourcing pipelines for expert contributors across high-value coding domains?" — and the narrower defensible question the data actually answers, with the distinction made explicit.

## 3. Why public open-source activity is directionally useful

Will argue the case for GH Archive event data as directional sourcing evidence: observable collaboration, verifiable activity, reproducibility at $0 — alongside what it cannot claim (workforce sizing, intrinsic quality, availability).

## 4. Data sources

Will document GH Archive via BigQuery Sandbox, GitHub GraphQL/REST enrichment, and offline location normalization, with actual bytes processed, API points used, and cache statistics from `reports/query_usage.csv` and `reports/enrichment_usage.csv`.

## 5. Repository taxonomy

Will describe the Cloud/DevOps subdomain taxonomy, the deterministic classification rules, and the measured precision and false-inclusion rate from the 150-repository manual validation.

## 6. Data funnel

Will show the real funnel counts: events → after bot removal → candidate repositories → activity-filtered → fully qualified → unique non-bot contributors → contributors with usable locations, against the pilot targets in `docs/product_spec.md`.

## 7. Scoring methodology

Will summarize the four score formulas (repository quality, contributor expert, geographic opportunity, confidence) with their exact configured weights, and link to `docs/methodology.md` for full definitions.

## 8. Validation

Will report data-quality checks, classification precision, location precision from the 500-string sample, and which acceptance gates passed or failed, without omission.

## 9. Findings

Will present the ranked countries (and qualifying cities) for Cloud/DevOps with opportunity and confidence side by side. For each recommended location: domain/subdomain, opportunity score, confidence score, observable expert count, repository and organization breadth, momentum, main caveat, and suggested sourcing experiment. Generated only from the frozen, validated dataset.

## 10. Recommended sourcing pilots

Will state at least three evidence-backed sourcing pilots in the executive-memo format: investigate [location] for [subdomain] contributors; evidence; confidence and reason; risk; suggested next step (small sourcing pilot validating response and qualification rates).

## 11. Sensitivity analysis

Will report ranking stability under the required perturbations — top-1% repository removal, largest-organization removal per country, ±20% weight variation, window comparison, raw-versus-weighted counts — and name any location whose rank changes materially.

## 12. Biases and limitations

Will restate the six representation limitations and the measured coverage biases from `docs/bias_limitations.md`, including the missing-location rate and any parsing bias found.

## 13. Next steps

Will lay out the expansion path: twelve-month window, additional domains (backend/distributed systems, C/C++ systems, CUDA/GPU, cybersecurity), refresh cadence, and what a sourcing-pilot feedback loop would add to the model.
