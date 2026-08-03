/**
 * Full static data contract for `web/public/data/**` per spec section 20.
 * These files are written by the publish pipeline and consumed read-only
 * by the frontend. Conventions across every file:
 *
 * - All field names are camelCase.
 * - Scores are 0-100 floats; shares/coverages are 0-1 floats.
 * - Counts are non-negative integers.
 *
 * Extends (does not replace) `types/manifest.ts` and `types/rankings.ts`.
 */

import type { GeographicRanking, GeoLevel, RecommendationTier } from "./rankings";

export type { Manifest, DatasetWindow, ManifestFiles } from "./manifest";
export type { GeographicRanking, GeoLevel, RecommendationTier };

/**
 * One row of `rankings/<domain>/{countries,cities}.json`,
 * `compare/<domain>.json`, and `locations/**` — the pipeline row
 * (spec 9.8) plus display fields the publish step adds for the web.
 */
export interface GeographicRankingRow extends GeographicRanking {
  /** Display name, e.g. "Germany" or "San Francisco". */
  name: string;
  /**
   * True when the momentum component was computed from an incomplete
   * window and must be labeled provisional in the UI.
   */
  momentumProvisional: boolean;
}

// ---------------------------------------------------------------------------
// summary.json
// ---------------------------------------------------------------------------

export interface SummaryKpis {
  qualifiedRepositories: number;
  observableExperts: number;
  /** 0-1 share of experts with a normalized location. */
  locatedProfileCoverage: number;
  countriesWithSufficientData: number;
}

export interface TopPriorityLocation {
  geoId: string;
  countryCode: string;
  name: string;
  opportunityScore: number;
  confidenceScore: number;
  tier: RecommendationTier;
}

export interface SubdomainHub {
  subdomainId: string;
  displayName: string;
  /** ISO alpha-2 code of the leading country for this subdomain. */
  topCountry: string;
  expertCount: number;
}

export interface Summary {
  domainId: string;
  window: import("./manifest").DatasetWindow;
  kpis: SummaryKpis;
  topPriorityLocations: TopPriorityLocation[];
  subdomainHubs: SubdomainHub[];
}

// ---------------------------------------------------------------------------
// rankings/<domain>/{countries,cities}.json
// ---------------------------------------------------------------------------

export interface RankingsFile {
  domainId: string;
  geoLevel: GeoLevel;
  generatedAt: string;
  rows: GeographicRankingRow[];
}

// ---------------------------------------------------------------------------
// locations/countries/<CC>.json and locations/cities/<slug>.json
// ---------------------------------------------------------------------------

/** The five 0-100 component scores behind the opportunity score. */
export interface ScoreComponents {
  expertSupplyScore: number;
  expertQualityScore: number;
  collaborationDepthScore: number;
  momentumScore: number;
  ecosystemBreadthScore: number;
}

export interface SubdomainMixEntry {
  subdomainId: string;
  displayName: string;
  expertCount: number;
  /** 0-1 share of the location's experts active in this subdomain. */
  share: number;
}

export interface ActivityTrendPoint {
  /** Calendar month, "YYYY-MM". */
  month: string;
  events: number;
  activeContributors: number;
}

export interface ConcentrationRisk {
  /** 0-1 share of weighted activity in the top organization. */
  topOrgShare: number;
  /** 0-1 share of experts observed in only one repository. */
  singleRepoShare: number;
  /** True when a concentration safeguard was triggered (spec 16). */
  flagged: boolean;
}

export interface CoverageStats {
  /** 0-1 share of experts with a normalized location. */
  locatedProfileCoverage: number;
  /** 0-1 share of located experts at high confidence. */
  highConfidenceLocationShare: number;
  observableExpertCount: number;
}

export interface LocationDetail {
  ranking: GeographicRankingRow;
  components: ScoreComponents;
  subdomainMix: SubdomainMixEntry[];
  activityTrend: ActivityTrendPoint[];
  concentration: ConcentrationRisk;
  coverage: CoverageStats;
  /** Human-readable data caveats to surface verbatim in the UI. */
  caveats: string[];
}

// ---------------------------------------------------------------------------
// compare/<domain>.json
// ---------------------------------------------------------------------------

/** Every rankable geography at both levels, for the compare picker. */
export interface CompareFile {
  rows: GeographicRankingRow[];
}

// ---------------------------------------------------------------------------
// methodology/validation.json
// ---------------------------------------------------------------------------

export interface QualityCheck {
  name: string;
  /** e.g. "pass" | "warn" | "fail" — kept open for pipeline additions. */
  status: string;
}

export interface FunnelStage {
  stage: string;
  count: number;
}

export interface ProcessingBudget {
  bytesProcessed: number;
  /** 0-1 share of the BigQuery free tier consumed. */
  freeTierShare: number;
}

export interface ValidationFile {
  /** 0-1 precision from the manual classification sample. */
  classificationPrecision: number;
  /** 0-1 precision of country-level location normalization. */
  locationCountryPrecision: number;
  /** 0-1 precision of city-level location normalization. */
  locationCityPrecision: number;
  qualityChecks: QualityCheck[];
  funnel: FunnelStage[];
  budget: ProcessingBudget;
}

// ---------------------------------------------------------------------------
// methodology/coverage.json
// ---------------------------------------------------------------------------

export interface CountryCoverage {
  countryCode: string;
  name: string;
  /** 0-1 located-profile share for this country. */
  share: number;
  expertCount: number;
}

export interface ConfidenceBucket {
  /** e.g. "high" | "medium" | "low". */
  level: string;
  count: number;
}

export interface CoverageFile {
  locatedShareByCountry: CountryCoverage[];
  confidenceDistribution: ConfidenceBucket[];
}

// ---------------------------------------------------------------------------
// recommendations/<domain>.json
// ---------------------------------------------------------------------------

export interface RecommendationItem {
  rank: number;
  geoId: string;
  name: string;
  subdomains: string[];
  opportunityScore: number;
  confidenceScore: number;
  /** Observable expert pool size backing the recommendation. */
  observablePool: number;
  whyNow: string;
  risk: string;
  suggestedPilot: string;
}

export interface RecommendationsFile {
  generatedAt: string;
  items: RecommendationItem[];
}
