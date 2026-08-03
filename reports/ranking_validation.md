# Ranking Validation — Cloud/DevOps Pilot (Milestone E)

**Dataset:** 2026.08.03-pilot.1 · **Window:** 2026-05-01 → 2026-07-31 · Sensitivity detail: [`sensitivity_rankings.csv`](sensitivity_rankings.csv)

## Headline rankings (countries, rankable only)

US (opp 67.3 / conf 58.1, monitor) · DE (64.1/70.6, promising) · IN (60.5/76.8, promising) · CN (60.2/68.1, promising) · GB · CA · FR · AU · PL · ES · IE · IL. 23 countries are rankable; 320 of 343 geographies fall below the spec minimum samples and are labeled `insufficient_data` with no normal rank. 5 cities rank (min samples 25/8/4 are strict at pilot scale — honest scarcity, not a defect).

**No location reaches the "priority" tier** (requires opportunity ≥75 AND confidence ≥70; pilot max opportunity is 71.1). The top of the board is "promising" — reported exactly as the configured thresholds dictate. Notably, the US tops opportunity but sits at "monitor" because its located-profile confidence (58.1) fails the ≥60 promising gate — the opportunity/confidence separation working as designed.

## Stability (spec 18 sensitivity tests)

| Scenario | Top-10 result vs baseline |
|---|---|
| Opportunity supply weight +20% (renormalized) | identical |
| Opportunity supply weight −20% | IN↔CN swap (3↔4), GB↔CA swap (5↔6) |
| Top 1% repositories by activity removed | IN↔CN swap (3↔4) |
| Largest organization removed (microsoft) | identical |

Maximum observed shift: **one position, among adjacent near-ties**. Rankings are stable; the IN/CN and GB/CA pairs are statistical ties and are disclosed as such.

## Gates

- Minimum-sample rules enforced: no low-sample geography carries a normal tier or rank.
- Opportunity and confidence never merged; both displayed everywhere.
- Component weights sum to configured totals (unit-tested); scores bounded 0–100.
- Contributor safeguards active: followers unused, single-repo share capped at 40%, push volume capped, ≥2 active days required, one-repo contributors marked.
- Classification gate: 92% precision / 4% false inclusion (150-repo review, `classification_validation.csv`).
- Location gates: 100% country and 100% city precision on high-confidence labels (500-string review, `location_validation.csv`).

## Known limitations carried into the rankings

- Momentum is provisional (month-over-month direction only; three-month pilot).
- `push_commit_count` unavailable in the 2026 GH Archive payload (decision B-04); push influence uses event counts, capped.
- Located-profile coverage is 46.6%; per-location coverage is displayed as confidence, never hidden.
