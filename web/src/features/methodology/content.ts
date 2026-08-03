/**
 * Static methodology content transcribed from the build specification.
 * This is methodology text (definitions, formulas, and documented
 * limitations) — NOT findings. No country scores, counts, or results
 * appear here; those come exclusively from published data files.
 */

/** Pipeline stages, condensed from the spec section 6 architecture flow. */
export const PIPELINE_STAGES: { name: string; detail: string }[] = [
  { name: "GH Archive monthly tables", detail: "Public GitHub event history" },
  { name: "BigQuery discovery SQL", detail: "Candidate repository activity" },
  { name: "GitHub GraphQL enrichment", detail: "Repository and user metadata" },
  { name: "Offline location normalization", detail: "Country and city resolution" },
  { name: "Repository and contributor scoring", detail: "Deterministic 0-100 scores" },
  { name: "Opportunity and confidence ranking", detail: "Country and city rankings" },
  { name: "Validation and bias checks", detail: "Precision, stability, coverage" },
  { name: "Static web datasets", detail: "Aggregate-only JSON for this app" },
];

export interface FormulaComponent {
  label: string;
  /** Exact configured weight in percent (spec sections 16-17). */
  weight: number;
}

export interface ScoreFormula {
  id: string;
  title: string;
  description: string;
  components: FormulaComponent[];
}

/**
 * The four score formulas with their EXACT configured weights
 * (spec 16.1, 16.2, and section 17). Each set sums to 100.
 */
export const SCORE_FORMULAS: ScoreFormula[] = [
  {
    id: "repository_quality",
    title: "Repository quality score",
    description:
      "How genuinely active, collaborative, and production-oriented a qualified repository is.",
    components: [
      { label: "Recent activity", weight: 30 },
      { label: "Contributor diversity", weight: 25 },
      { label: "Collaboration quality", weight: 20 },
      { label: "Technical relevance", weight: 15 },
      { label: "Repository maturity", weight: 10 },
    ],
  },
  {
    id: "expert_score",
    title: "Contributor expert score",
    description:
      "Domain-specific contributor evidence. Contribution quality is event-type evidence, not intrinsic developer quality.",
    components: [
      { label: "Domain activity", weight: 35 },
      { label: "Contribution quality", weight: 25 },
      { label: "Repository quality exposure", weight: 20 },
      { label: "Continuity", weight: 10 },
      { label: "Collaboration", weight: 10 },
    ],
  },
  {
    id: "opportunity_score",
    title: "Opportunity score",
    description:
      "Location-level sourcing opportunity, computed separately by domain and geography.",
    components: [
      { label: "Expert supply", weight: 35 },
      { label: "Expert quality", weight: 30 },
      { label: "Collaboration depth", weight: 15 },
      { label: "Momentum", weight: 10 },
      { label: "Ecosystem breadth", weight: 10 },
    ],
  },
  {
    id: "confidence_score",
    title: "Confidence score",
    description:
      "How much to trust a location's data — always published separately from opportunity, never merged.",
    components: [
      { label: "Located profile coverage", weight: 35 },
      { label: "Location certainty", weight: 25 },
      { label: "Sample size adequacy", weight: 20 },
      { label: "Repository diversity", weight: 10 },
      { label: "Organization diversity", weight: 10 },
    ],
  },
];

/** Repository inclusion rules, condensed from spec section 12. */
export const INCLUSION_RULES: string[] = [
  "Public, not a fork, not archived or disabled",
  "Active within the selected window, in at least two months of the pilot",
  "At least five unique human contributors",
  "At least twenty meaningful events",
  "At least three pull requests or reviews",
  "Clearly related to at least one Cloud/DevOps subdomain",
  "Covered by a recognized open-source license",
];

/** Repository exclusion rules, condensed from spec section 12. */
export const EXCLUSION_RULES: string[] = [
  "Bots and automation accounts",
  "Dotfiles, tutorial-only projects, and student assignments",
  "Interview-preparation repositories and awesome lists",
  "Documentation-only repositories, mirrors, and generated copies",
  "Abandoned repositories",
  "Repositories where one actor accounts for more than 90% of meaningful activity",
  "Repositories with suspicious burst patterns",
  "Repositories unrelated to production engineering",
];

/**
 * The six representation limitations, verbatim from spec section 18.
 * The spec requires these to be visible in the product, not hidden in
 * the repository.
 */
export const REPRESENTATION_LIMITATIONS: string[] = [
  "GitHub activity is not the total developer workforce.",
  "Public contribution behavior differs by region and employer.",
  "Self-reported locations may be missing, stale, humorous, or ambiguous.",
  "Event volume does not directly measure engineering quality.",
  "Open-source expertise may not equal availability or willingness to contract.",
  "Some domains are underrepresented in public repositories.",
];
