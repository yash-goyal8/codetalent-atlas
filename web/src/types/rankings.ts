/**
 * Geographic ranking record, mirroring the pipeline schema in spec
 * section 9.8. Field names are camelCase in the published web JSON
 * (matching the manifest example in spec section 20); the snake_case
 * originals are noted where the mapping is not obvious.
 *
 * Consumed by Explorer, ranking rails, and detail routes starting in
 * Milestone F. Unused until then.
 */

export type GeoLevel = "country" | "city";

export type RecommendationTier =
  | "priority"
  | "promising"
  | "monitor"
  | "insufficient_data";

export interface GeographicRanking {
  geoLevel: GeoLevel;
  geoId: string;
  countryCode: string;
  city: string | null;
  domainId: string;
  /** All scores use a consistent 0-100 scale. */
  opportunityScore: number;
  confidenceScore: number;
  expertSupplyScore: number;
  expertQualityScore: number;
  collaborationDepthScore: number;
  momentumScore: number;
  ecosystemBreadthScore: number;
  observableExpertCount: number;
  weightedExpertCount: number;
  qualifiedRepoCount: number;
  organizationCount: number;
  /** 0-1 share; snake_case original: multi_repo_expert_share. */
  multiRepoExpertShare: number;
  /** 0-1 share; snake_case original: located_profile_coverage. */
  locatedProfileCoverage: number;
  /** 0-1 share; snake_case original: high_confidence_location_share. */
  highConfidenceLocationShare: number;
  topSubdomains: string[];
  rank: number;
  recommendationTier: RecommendationTier;
}
