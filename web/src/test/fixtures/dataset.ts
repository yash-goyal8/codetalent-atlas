/**
 * SYNTHETIC TEST FIXTURE — not real results.
 *
 * One coherent fake dataset covering every file in the spec section 20
 * contract, for unit tests (and Playwright route interception later).
 * Country codes are real ISO alpha-2 codes (US, DE, IN) ONLY so that
 * geo joins against public/geo/countries.geojson work in tests; every
 * score/count is a transparently arbitrary round number (90/80/70
 * ladders) and none of it reflects pipeline output. This module must
 * never be imported by product code or copied into web/public.
 */

import type { Manifest } from "../../types/manifest";
import type {
  CompareFile,
  CoverageFile,
  GeographicRankingRow,
  LocationDetail,
  RankingsFile,
  RecommendationsFile,
  Summary,
  ValidationFile,
} from "../../types/data";

export const SYNTHETIC_NOTE = "SYNTHETIC TEST FIXTURE — not real results";

export const syntheticManifest: Manifest = {
  datasetVersion: "0000.00.00-synthetic.1",
  generatedAt: "2000-01-01T00:00:00Z",
  window: { start: "2000-01-01", end: "2000-03-31" },
  domains: ["cloud_devops"],
  files: {
    summary: "summary.json",
    countryRankings: "rankings/cloud_devops/countries.json",
    cityRankings: "rankings/cloud_devops/cities.json",
    compare: "compare/cloud_devops.json",
    validation: "methodology/validation.json",
    coverage: "methodology/coverage.json",
    recommendations: "recommendations/cloud_devops.json",
  },
  methodologyVersion: "0.0.0-synthetic",
};

function countryRow(
  overrides: Partial<GeographicRankingRow> &
    Pick<GeographicRankingRow, "geoId" | "countryCode" | "name" | "rank">,
): GeographicRankingRow {
  return {
    geoLevel: "country",
    city: null,
    domainId: "cloud_devops",
    opportunityScore: 90,
    confidenceScore: 80,
    expertSupplyScore: 90,
    expertQualityScore: 80,
    collaborationDepthScore: 70,
    momentumScore: 60,
    ecosystemBreadthScore: 50,
    observableExpertCount: 900,
    weightedExpertCount: 800,
    qualifiedRepoCount: 90,
    organizationCount: 40,
    multiRepoExpertShare: 0.5,
    locatedProfileCoverage: 0.4,
    highConfidenceLocationShare: 0.6,
    topSubdomains: ["containers", "ci_cd"],
    recommendationTier: "priority",
    momentumProvisional: false,
    ...overrides,
  };
}

/** Synthetic country rows: US > DE > IN with obviously stepped scores. */
export const syntheticCountryRows: GeographicRankingRow[] = [
  countryRow({
    geoId: "US",
    countryCode: "US",
    name: "United States",
    rank: 1,
    opportunityScore: 90,
    confidenceScore: 80,
    recommendationTier: "priority",
  }),
  countryRow({
    geoId: "DE",
    countryCode: "DE",
    name: "Germany",
    rank: 2,
    opportunityScore: 80,
    confidenceScore: 70,
    observableExpertCount: 500,
    weightedExpertCount: 400,
    topSubdomains: ["observability", "containers"],
    recommendationTier: "promising",
  }),
  countryRow({
    geoId: "IN",
    countryCode: "IN",
    name: "India",
    rank: 3,
    opportunityScore: 70,
    confidenceScore: 50,
    observableExpertCount: 700,
    weightedExpertCount: 550,
    topSubdomains: ["ci_cd", "cloud_platforms"],
    recommendationTier: "monitor",
    momentumProvisional: true,
  }),
];

export const syntheticCityRows: GeographicRankingRow[] = [
  countryRow({
    geoLevel: "city",
    geoId: "US/testville",
    countryCode: "US",
    city: "Testville",
    name: "Testville",
    rank: 1,
    observableExpertCount: 300,
    weightedExpertCount: 250,
  }),
  countryRow({
    geoLevel: "city",
    geoId: "DE/examplestadt",
    countryCode: "DE",
    city: "Examplestadt",
    name: "Examplestadt",
    rank: 2,
    opportunityScore: 75,
    confidenceScore: 65,
    observableExpertCount: 200,
    weightedExpertCount: 150,
    recommendationTier: "promising",
  }),
];

export const syntheticSummary: Summary = {
  domainId: "cloud_devops",
  window: syntheticManifest.window,
  kpis: {
    qualifiedRepositories: 1000,
    observableExperts: 2000,
    locatedProfileCoverage: 0.4,
    countriesWithSufficientData: 3,
  },
  topPriorityLocations: syntheticCountryRows.map((row) => ({
    geoId: row.geoId,
    countryCode: row.countryCode,
    name: row.name,
    opportunityScore: row.opportunityScore,
    confidenceScore: row.confidenceScore,
    tier: row.recommendationTier,
  })),
  subdomainHubs: [
    {
      subdomainId: "containers",
      displayName: "Containers and orchestration",
      topCountry: "US",
      expertCount: 800,
    },
    {
      subdomainId: "observability",
      displayName: "Observability and monitoring",
      topCountry: "DE",
      expertCount: 400,
    },
  ],
};

export const syntheticCountryRankings: RankingsFile = {
  domainId: "cloud_devops",
  geoLevel: "country",
  generatedAt: syntheticManifest.generatedAt,
  rows: syntheticCountryRows,
};

export const syntheticCityRankings: RankingsFile = {
  domainId: "cloud_devops",
  geoLevel: "city",
  generatedAt: syntheticManifest.generatedAt,
  rows: syntheticCityRows,
};

/** Detail file for the synthetic top country (US). */
export const syntheticLocationDetail: LocationDetail = {
  ranking: syntheticCountryRows[0],
  components: {
    expertSupplyScore: 90,
    expertQualityScore: 80,
    collaborationDepthScore: 70,
    momentumScore: 60,
    ecosystemBreadthScore: 50,
  },
  subdomainMix: [
    {
      subdomainId: "containers",
      displayName: "Containers and orchestration",
      expertCount: 500,
      share: 0.5,
    },
    {
      subdomainId: "ci_cd",
      displayName: "CI/CD and developer tooling",
      expertCount: 300,
      share: 0.3,
    },
    {
      subdomainId: "observability",
      displayName: "Observability and monitoring",
      expertCount: 200,
      share: 0.2,
    },
  ],
  activityTrend: [
    { month: "2000-01", events: 1000, activeContributors: 100 },
    { month: "2000-02", events: 2000, activeContributors: 200 },
    { month: "2000-03", events: 3000, activeContributors: 300 },
  ],
  concentration: { topOrgShare: 0.2, singleRepoShare: 0.5, flagged: false },
  coverage: {
    locatedProfileCoverage: 0.4,
    highConfidenceLocationShare: 0.6,
    observableExpertCount: 900,
  },
  caveats: [
    "Synthetic caveat one — fixture text only.",
    "Synthetic caveat two — fixture text only.",
  ],
};

export const syntheticCompare: CompareFile = {
  rows: [...syntheticCountryRows, ...syntheticCityRows],
};

export const syntheticValidation: ValidationFile = {
  classificationPrecision: 0.9,
  locationCountryPrecision: 0.9,
  locationCityPrecision: 0.8,
  qualityChecks: [
    { name: "Synthetic check A", status: "pass" },
    { name: "Synthetic check B", status: "warn" },
  ],
  funnel: [
    { stage: "Candidate repositories", count: 10000 },
    { stage: "Qualified repositories", count: 1000 },
    { stage: "Observable experts", count: 2000 },
  ],
  budget: { bytesProcessed: 1_000_000_000, freeTierShare: 0.1 },
};

export const syntheticCoverage: CoverageFile = {
  locatedShareByCountry: [
    { countryCode: "US", name: "United States", share: 0.4, expertCount: 900 },
    { countryCode: "DE", name: "Germany", share: 0.5, expertCount: 500 },
    { countryCode: "IN", name: "India", share: 0.3, expertCount: 700 },
  ],
  confidenceDistribution: [
    { level: "high", count: 1200 },
    { level: "medium", count: 500 },
    { level: "low", count: 300 },
  ],
};

export const syntheticRecommendations: RecommendationsFile = {
  generatedAt: syntheticManifest.generatedAt,
  items: [
    {
      rank: 1,
      geoId: "US",
      name: "United States",
      subdomains: ["containers", "ci_cd"],
      opportunityScore: 90,
      confidenceScore: 80,
      observablePool: 900,
      whyNow: "Synthetic why-now rationale — fixture text only.",
      risk: "Synthetic risk statement — fixture text only.",
      suggestedPilot: "Synthetic pilot suggestion — fixture text only.",
    },
    {
      rank: 2,
      geoId: "DE",
      name: "Germany",
      subdomains: ["observability"],
      opportunityScore: 80,
      confidenceScore: 70,
      observablePool: 500,
      whyNow: "Synthetic why-now rationale — fixture text only.",
      risk: "Synthetic risk statement — fixture text only.",
      suggestedPilot: "Synthetic pilot suggestion — fixture text only.",
    },
  ],
};
