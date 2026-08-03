# Classification Manual-Validation Rubric (v1)

Used for the 150-repository stratified review required by spec Phase 2
(50 auto-accepted / 50 auto-rejected / 50 borderline; sample seed 150, stored
at `data/interim/classification_validation_sample.parquet`; labels in
`reports/classification_validation.csv`).

## Labels

- **relevant** — the repository is clearly production-oriented tooling,
  infrastructure, or platform code for at least one Cloud/DevOps subdomain
  (IaC, containers/orchestration, CI/CD & developer tooling, observability,
  configuration management, service mesh/networking, cloud platforms/SDKs,
  SRE), judged from name, description, topics, and classifier evidence.
- **not_relevant** — out of domain (application frameworks, databases,
  end-user products, other engineering domains) or an excluded category per
  spec section 12: tutorial/course material, student assignments, awesome
  lists, documentation-only, dotfiles, interview prep.
- **unsure** — defensible either way; counted AGAINST precision (strict).
- **correct_rejection / missed_relevant** — for the rejected stratum only.

## Reviewer and honesty note

Labels were assigned by the build agent applying this rubric to repository
name, description, topics, and classifier evidence — not by a second human.
The rubric, sample, and every label are committed so any human can re-audit
and overturn individual judgments; the gate margin (92% vs the 90% bar)
should be read with that limitation in mind (also recorded in
`docs/bias_limitations.md`).

## Results (2026-08-03)

- Domain-classification precision (accepted stratum, strict): **92.0%** (gate ≥90% — PASS)
- False inclusion rate: **4.0%** (gate <10% — PASS)
- Missed-relevant in the rejected sample: 2/50 (recall caveat: repositories
  whose names/descriptions lack taxonomy terms, e.g. APM agents named after
  the vendor; noted for Milestone C+ taxonomy iteration)
- Borderline stratum: 13/50 judged relevant — the borderline queue is real
  review inventory, not noise; qualified set remains auto-accepted-only for
  the pilot (documented shortfall vs the 1,000+ aspiration in the report).
