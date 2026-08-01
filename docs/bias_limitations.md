# CodeTalent Atlas — Bias and Limitations

**Status:** Seeded in Milestone A with the representation limitations that hold regardless of any measurement. Coverage-bias measurements are planned and marked below; they are produced in Milestone E from the real dataset. This document contains no findings and no numbers until then.

These limitations are surfaced in the product itself (methodology page and limitations notes), not only in this repository.

---

## 1. Representation limitations

These are structural properties of the data source, documented per spec section 18:

1. GitHub activity is not the total developer workforce.
2. Public contribution behavior differs by region and employer.
3. Self-reported locations may be missing, stale, humorous, or ambiguous.
4. Event volume does not directly measure engineering quality.
5. Open-source expertise may not equal availability or willingness to contract.
6. Some domains are underrepresented in public repositories.

Consequences for interpretation:

- Rankings describe **observable, active contributors to qualified public repositories** — not developer populations. A low-ranked location may simply have a culture or employer base that contributes less publicly.
- The expert score's quality component is contribution-quality *evidence* from event types, never a claim of intrinsic engineering quality.
- Recommendations are starting points for sourcing pilots, whose response and qualification rates are the actual test of availability.

## 2. Coverage-bias measurements (planned)

To be measured in **Milestone E** on the validated pilot dataset and reported here and in `reports/ranking_validation.md`. No values are assumed in advance — including the 40% usable-location target, which is a target, not a fact.

| Measurement | What it detects | Status |
|---|---|---|
| Missing public-location rate | Overall share of contributors invisible to geographic aggregation | to be measured — Milestone E |
| Location coverage by activity decile | Whether highly active contributors disclose locations at different rates, biasing supply scores | to be measured — Milestone E |
| Location coverage by primary language | Whether some language ecosystems are systematically less locatable | to be measured — Milestone E |
| Location coverage by organization size | Whether large-organization contributors disclose differently, biasing ecosystem scores | to be measured — Milestone E |
| Country-name and English-language parsing bias | Whether the offline normalizer resolves English-language and Latin-script locations at higher rates, deflating non-English regions | to be measured — Milestone E |

Each measurement feeds the confidence score (located-profile coverage, location certainty) so that coverage weaknesses lower confidence rather than silently distorting opportunity.

## 3. Known structural biases to monitor

Identified in advance so the Milestone E analysis must address them explicitly:

- **Popularity distortion:** a few dominant repositories can dominate raw counts; mitigated by winsorization, per-repository caps, and concentration flags — effectiveness verified by sensitivity tests (drop top 1% of repositories; drop largest organization per country).
- **Automation residue:** bot filtering is pattern-based and cannot be perfect; residual automation share is reported per repository (`automation_event_share`).
- **Pilot-window momentum:** three months supports only provisional month-over-month momentum; momentum is labeled provisional until the twelve-month expansion.
- **City-level sparsity:** city rankings use high-confidence locations only and stricter sample minimums; cities below threshold are labeled `insufficient_data` rather than ranked on thin evidence.

## 4. Disclosure rules

- No recommendation is published without a confidence score.
- Ranking instability found in sensitivity tests is disclosed, not smoothed over.
- If the 40% usable-location target proves infeasible, that finding is documented and published rather than worked around.
