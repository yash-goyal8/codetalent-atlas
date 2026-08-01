# CodeTalent Atlas — Product Specification

**Status:** Phase 0 deliverable. Locked before any data work begins.
**Source of truth:** [`docs/CODETALENT_ATLAS_BUILD_SPEC.md`](CODETALENT_ATLAS_BUILD_SPEC.md). This document summarizes the product definition; the build spec governs on any conflict.

---

## 1. Core question

> Where should Scale investigate and build sourcing pipelines for expert contributors across high-value coding domains?

Raw GitHub counts cannot answer this directly: popularity, automation, duplicated forks, incomplete locations, and a few dominant repositories distort naive counts. The product therefore answers a narrower, defensible question and is explicit about the difference:

> Among observable, active contributors to qualified public repositories, which locations show the strongest combination of expert supply, quality, collaboration depth, momentum, and ecosystem breadth for a selected coding domain?

Every ranking, score, and recommendation in the product is an answer to the narrower question, offered as directional evidence for the core question — never as a measurement of the total developer labor market.

## 2. Primary user and use cases

The primary user is a sourcing or program leader at Scale who needs location-level evidence, not individual candidates. Supported use cases:

1. **Contributor sourcing** — decide where to stand up sourcing pipelines for expert coding contributors, with explicit confidence attached to every location.
2. **Coding-data operations** — size and plan data-production programs that depend on domain experts (for the pilot: Cloud and DevOps).
3. **Market research** — understand the geographic shape of observable open-source expertise in a domain: supply, quality, momentum, and ecosystem breadth.
4. **Program planning** — prioritize a small number of location pilots, each backed by reconstructible scores and a stated main risk.

The product deliberately does not serve individual-recruiter workflows. It never ranks or displays individual developers.

## 3. Pilot scope

- **Domain:** Cloud and DevOps only. Eight subdomains: Infrastructure as Code; Containers and orchestration; CI/CD and developer tooling; Observability and monitoring; Configuration management; Service mesh and networking; Cloud platforms and SDKs; SRE and reliability engineering.
- **Window:** 2026-05-01 through 2026-07-31 (three months).
- **Parameterization:** the pipeline is parameterized so the validated version expands to twelve months and additional domains (backend/distributed systems, C/C++ systems, CUDA/GPU, cybersecurity) without redesign. Expansion domains are not implemented before the pilot passes its acceptance gates.

## 4. Dataset targets

Pilot (spec section 3.3):

| Target | Threshold |
|---|---|
| Discovered candidate repositories | 10,000+ |
| Repositories passing activity filters | 5,000+ |
| Repositories passing full Cloud/DevOps relevance and quality filters | 1,000+ |
| Unique non-bot contributors | 5,000+ |
| Usable country-level public locations | 40%+, or a documented finding that the threshold is infeasible |

Expanded (post-pilot):

- 10,000–25,000 qualified repositories across all domains
- 50,000–150,000 contributor-domain records
- Country rankings for all adequately sampled locations
- City rankings only where sample size and parsing confidence are sufficient

## 5. Non-goals

Verbatim from spec section 3.4. Do not:

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

## 6. Success criteria

The project succeeds only if it delivers all of the following (spec section 4):

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

## 7. Hard constraint: $0 total cost

The complete project must cost exactly **$0** to build, process, host, refresh, and demonstrate. No paid API, paid database, paid map provider, paid model, paid domain, paid hosting feature, or any service that requires billing activation — including services with free trials that can create a charge. Concretely: GH Archive via BigQuery Sandbox (no billing attached), GitHub GraphQL/REST within free authenticated limits, offline location normalization, GitHub Actions on a public repository, and Cloudflare Pages static hosting on a free `pages.dev` URL.

## 8. Output policy

The public deployment exposes **aggregates only**: location-level scores, counts, and summaries. Individual developers are never ranked or displayed, and no username, raw location string, or profile URL appears in any public asset. See [`docs/privacy_ethics.md`](privacy_ethics.md) for the full policy and the automated scanner that enforces it.
