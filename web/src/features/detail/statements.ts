/**
 * Templated statements for the location detail page. Every sentence is
 * assembled from tier definitions (spec section 17) or the location's
 * actual published values — no free-form invention, no model calls.
 */

import { confidenceLabel, formatScore, formatShare } from "../../lib/format";
import type {
  LocationDetail,
  RecommendationTier,
  ScoreComponents,
} from "../../types/data";

/** Display labels for the five opportunity components. */
export const COMPONENT_LABELS: Record<keyof ScoreComponents, string> = {
  expertSupplyScore: "Expert supply",
  expertQualityScore: "Expert quality",
  collaborationDepthScore: "Collaboration depth",
  momentumScore: "Momentum",
  ecosystemBreadthScore: "Ecosystem breadth",
};

const COMPONENT_KEYS = Object.keys(
  COMPONENT_LABELS,
) as (keyof ScoreComponents)[];

/**
 * Concise recommendation statement per tier — direct restatements of
 * the configured tier definitions (spec 17), not findings.
 */
const TIER_STATEMENTS: Record<RecommendationTier, string> = {
  priority:
    "Priority sourcing location: high opportunity backed by sufficient data confidence.",
  promising:
    "Promising sourcing location: strong signals; confidence supports a small pilot.",
  monitor:
    "Monitor: opportunity or confidence is not yet strong enough to recommend a sourcing pilot.",
  insufficient_data:
    "Insufficient data: below the minimum sample thresholds for a reliable recommendation.",
};

export function tierStatement(tier: RecommendationTier): string {
  return TIER_STATEMENTS[tier];
}

/** Strongest and weakest of the five components, by actual value. */
export function extremeComponents(components: ScoreComponents): {
  strongest: keyof ScoreComponents;
  weakest: keyof ScoreComponents;
} {
  let strongest = COMPONENT_KEYS[0];
  let weakest = COMPONENT_KEYS[0];
  for (const key of COMPONENT_KEYS) {
    if (components[key] > components[strongest]) strongest = key;
    if (components[key] < components[weakest]) weakest = key;
  }
  return { strongest, weakest };
}

/**
 * "Why this location ranks here" — sentences templated exclusively from
 * the location's published numbers (spec 19.4 section 7).
 */
export function whyStatements(detail: LocationDetail): string[] {
  const { ranking, components, coverage } = detail;
  const { strongest, weakest } = extremeComponents(components);
  const levelWord = ranking.geoLevel === "country" ? "countries" : "cities";

  const sentences = [
    `${ranking.name} ranks #${ranking.rank} among ranked ${levelWord} for Cloud and DevOps with an opportunity score of ${formatScore(ranking.opportunityScore)}.`,
    `Its strongest component is ${COMPONENT_LABELS[strongest].toLowerCase()} (${formatScore(components[strongest])}); its weakest is ${COMPONENT_LABELS[weakest].toLowerCase()} (${formatScore(components[weakest])}).`,
    `Confidence is ${formatScore(ranking.confidenceScore)} (${confidenceLabel(ranking.confidenceScore).toLowerCase()}): ${formatShare(coverage.locatedProfileCoverage)} of observable experts have a usable location, and ${formatShare(coverage.highConfidenceLocationShare)} of those locations are high-confidence.`,
  ];
  if (ranking.momentumProvisional) {
    sentences.push(
      "Momentum is provisional: the pilot window is too short for a full trend comparison.",
    );
  }
  return sentences;
}
