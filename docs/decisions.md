# CodeTalent Atlas — Decision Log

Append-only log of implementation decisions, deviations, and gaps. Required by build-spec operating instructions 4 and 13. Newest entries at the bottom of each dated section.

Format: date, decision, rationale, and (where relevant) the milestone that revisits it.

---

## 2026-08-01 — Milestone A (repository foundation)

### A-01: Python floor stays at >=3.12 despite local 3.13.5

Local interpreter is Python 3.13.5. `pyproject.toml` keeps `requires-python = ">=3.12"` as the spec's stated floor (section 5.3) rather than raising it to 3.13. Rationale: the spec requires 3.12+, and a lower floor keeps the repo runnable on standard CI images and fresh clones without forcing the newest minor version. Code must therefore avoid 3.13-only features.

### A-02: Toolchain installs — uv via Homebrew, pnpm via npm (corepack broken)

uv 0.12.1 installed via Homebrew. pnpm 10 installed globally via npm because the corepack shim fails on Node 20.18.0 with `ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING`. Rationale: corepack is the usual route but is unusable on this Node version; a direct npm install of pnpm yields the same pinned-lockfile behavior. Both installs are free and documented so a fresh machine can reproduce them.

### A-03: Vite pinned to ^6

Node is 20.18.0, below Vite 7's minimum of 20.19. Vite is pinned to `^6` in `web/package.json`. Rationale: Vite 6 is fully supported on Node 20.18 and satisfies every frontend requirement in the spec; upgrading to Vite 7 is a one-line change once the Node runtime moves past 20.19. Revisit at Milestone F if the runtime changes.

### A-04: shadcn/ui primitives added manually

shadcn/ui components are vendored manually into `web/src/components` rather than generated with the interactive `shadcn` CLI. Rationale: the CLI is interactive and unsuited to a deterministic, scripted setup; manual vendoring pins exact component source in the repository, which matches the spec's reproducibility requirements.

### A-05: MapLibre GL, ECharts, and Framer Motion deferred to Milestone F

The Milestone A frontend shell excludes MapLibre GL JS, Apache ECharts, and Framer Motion. Rationale: none are exercised until real aggregate data and the full UI exist (Milestone F); deferring them keeps the shell lean, the dependency surface auditable, and the initial builds fast. The spec's frontend stack (section 5.5) is unchanged — only the installation point moves.

### A-06: Playwright E2E deferred to Milestone F

Playwright and the required E2E flows (spec section 20) are deferred to Milestone F. Rationale: every required flow (select domain, filter explorer, open detail, compare, methodology, username scan) depends on the real data UI, which does not exist until Milestone F. Vitest unit/component testing is in place from Milestone A.

### A-07: `web/public/social-card.png` deferred to Milestone F

The social card image listed in the repository structure (spec section 7) is not created in Milestone A. Rationale: no brand visuals exist yet; committing a placeholder image would violate the no-junk quality bar. Created in Milestone F alongside the visual system.

### A-08: `sql/` query templates deferred to Milestone B

The seven SQL files under `sql/` (spec section 7) are not stubbed in Milestone A. Rationale: the spec's implementation order (section 29) assigns SQL templates and the dry-run guard to Milestone B; empty SQL stubs would add nothing and risk being mistaken for runnable queries.

### A-09: Privacy scanner implemented early, in Milestone A

The public-data privacy scanner (spec section 27) is implemented in Milestone A even though no public data exists yet. Rationale: implementing the guard before any data stage exists means every later milestone is born under it; there is no window in which public assets can be produced unscanned. The scan runs in CI from the first commit.

### A-10: Taxonomy positive/negative example tests deferred to Milestone C

Spec section 8.1 requires tests proving known positive and negative classification examples. These are deferred to Milestone C. Rationale: the tests exercise the deterministic classifier, which is a Milestone C deliverable; writing them earlier would test configuration files against code that does not exist.

### A-11: Structured logging module named `runlog.py`

The structured JSON-lines logging module (spec section 26) is named `runlog.py` rather than `logging.py`. Rationale: a module named `logging` inside the package would shadow the stdlib `logging` module and invite subtle import bugs. The spec does not mandate a module name; the required log fields are unchanged.
