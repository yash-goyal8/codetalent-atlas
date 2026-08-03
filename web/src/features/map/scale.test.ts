import { describe, expect, it } from "vitest";
import type { GeographicRankingRow } from "../../types/data";
import { syntheticCountryRows } from "../../test/fixtures/dataset";
import {
  cityFeatureCollection,
  CITY_MAX_RADIUS,
  CITY_MIN_RADIUS,
  colorForScore,
  countryFillColor,
  countryFillOpacity,
  countryIdFilter,
  countryPointFeatureCollection,
  DATA_FILL_OPACITY,
  isLowConfidence,
  LOW_CONFIDENCE_FILL_OPACITY,
  lowConfidenceCountryFilter,
  MICROSTATE_RADIUS,
  NO_DATA_FILL,
  scoreForLayer,
  SEQUENTIAL_RAMP,
  subdomainLabel,
  type CityCoordinateFields,
} from "./scale";
import { MICROSTATE_CENTROIDS } from "./microstates";

/** Synthetic city row with centroid coordinates for point-layer tests. */
function cityRow(
  overrides: Partial<GeographicRankingRow & CityCoordinateFields> &
    Pick<GeographicRankingRow, "geoId" | "name">,
): GeographicRankingRow & CityCoordinateFields {
  return {
    ...syntheticCountryRows[0],
    geoLevel: "city",
    countryCode: "US",
    city: overrides.name,
    rank: 1,
    ...overrides,
  };
}

describe("colorForScore", () => {
  it("maps the scale endpoints onto the ramp endpoints", () => {
    expect(colorForScore(0)).toBe(SEQUENTIAL_RAMP[0]);
    expect(colorForScore(100)).toBe(SEQUENTIAL_RAMP[SEQUENTIAL_RAMP.length - 1]);
  });

  it("hits the intermediate stops at even quarters", () => {
    expect(colorForScore(25)).toBe(SEQUENTIAL_RAMP[1]);
    expect(colorForScore(75)).toBe(SEQUENTIAL_RAMP[3]);
  });

  it("clamps out-of-range and non-finite input", () => {
    expect(colorForScore(-10)).toBe(SEQUENTIAL_RAMP[0]);
    expect(colorForScore(250)).toBe(SEQUENTIAL_RAMP[SEQUENTIAL_RAMP.length - 1]);
    expect(colorForScore(Number.NaN)).toBe(SEQUENTIAL_RAMP[0]);
  });
});

describe("scoreForLayer", () => {
  it("selects the matching 0-100 field per layer", () => {
    const row = syntheticCountryRows[0];
    expect(scoreForLayer(row, "opportunity")).toBe(row.opportunityScore);
    expect(scoreForLayer(row, "supply")).toBe(row.expertSupplyScore);
    expect(scoreForLayer(row, "quality")).toBe(row.expertQualityScore);
    expect(scoreForLayer(row, "momentum")).toBe(row.momentumScore);
    expect(scoreForLayer(row, "confidence")).toBe(row.confidenceScore);
  });
});

describe("subdomainLabel", () => {
  it("uses the pilot taxonomy display names for known ids", () => {
    expect(subdomainLabel("observability_monitoring")).toBe(
      "Observability and Monitoring",
    );
    expect(subdomainLabel("infrastructure_as_code")).toBe(
      "Infrastructure as Code",
    );
    expect(subdomainLabel("cicd_developer_tooling")).toBe(
      "CI/CD and Developer Tooling",
    );
    expect(subdomainLabel("cloud_platforms_sdks")).toBe(
      "Cloud Platforms and SDKs",
    );
  });

  it("prettifies unknown ids mechanically", () => {
    expect(subdomainLabel("containers")).toBe("Containers");
    expect(subdomainLabel("ci_cd")).toBe("CI CD");
    expect(subdomainLabel("platform_of_things")).toBe("Platform of Things");
  });
});

describe("isLowConfidence", () => {
  it("is false for medium and high confidence rows", () => {
    // Synthetic rows: confidence 80/70/50 with tiers above insufficient_data.
    for (const row of syntheticCountryRows) {
      expect(isLowConfidence(row)).toBe(false);
    }
  });

  it("is true below the low-confidence threshold or for insufficient data", () => {
    expect(
      isLowConfidence({ ...syntheticCountryRows[0], confidenceScore: 30 }),
    ).toBe(true);
    expect(
      isLowConfidence({
        ...syntheticCountryRows[0],
        recommendationTier: "insufficient_data",
      }),
    ).toBe(true);
  });
});

describe("country choropleth expressions", () => {
  it("builds a match expression keyed by geoId with a no-data fallback", () => {
    const expression = countryFillColor(syntheticCountryRows, "opportunity");
    expect(Array.isArray(expression)).toBe(true);
    const flat = expression as unknown[];
    expect(flat[0]).toBe("match");
    expect(flat).toContain("US");
    expect(flat).toContain("DE");
    expect(flat).toContain("IN");
    expect(flat[flat.length - 1]).toBe(NO_DATA_FILL);
  });

  it("falls back to the transparent fill with no rows", () => {
    expect(countryFillColor([], "opportunity")).toBe(NO_DATA_FILL);
    expect(countryFillOpacity([])).toBe(1);
  });

  it("fades low-confidence countries via the opacity expression", () => {
    const rows = [
      syntheticCountryRows[0],
      { ...syntheticCountryRows[1], confidenceScore: 20 },
    ];
    const expression = countryFillOpacity(rows) as unknown[];
    const usIndex = expression.indexOf("US");
    const deIndex = expression.indexOf("DE");
    expect(expression[usIndex + 1]).toBe(DATA_FILL_OPACITY);
    expect(expression[deIndex + 1]).toBe(LOW_CONFIDENCE_FILL_OPACITY);
  });

  it("selects only low-confidence countries for the dashed-border layer", () => {
    const rows = [
      syntheticCountryRows[0],
      { ...syntheticCountryRows[1], confidenceScore: 20 },
    ];
    const filter = lowConfidenceCountryFilter(rows) as unknown[];
    expect(JSON.stringify(filter)).toContain("DE");
    expect(JSON.stringify(filter)).not.toContain("US");
  });

  it("countryIdFilter never matches when no geo is selected", () => {
    expect(JSON.stringify(countryIdFilter(null))).toContain("__none__");
    expect(JSON.stringify(countryIdFilter("US"))).toContain("US");
  });
});

describe("cityFeatureCollection", () => {
  it("skips city rows without centroid coordinates", () => {
    const collection = cityFeatureCollection(
      [cityRow({ geoId: "US-testville", name: "Testville" })],
      "opportunity",
    );
    expect(collection.features).toHaveLength(0);
  });

  it("sizes points by observable expert count between the radius bounds", () => {
    const rows = [
      cityRow({
        geoId: "US/big",
        name: "Big",
        longitude: -100,
        latitude: 40,
        observableExpertCount: 400,
      }),
      cityRow({
        geoId: "US/small",
        name: "Small",
        longitude: -90,
        latitude: 35,
        observableExpertCount: 100,
      }),
    ];
    const collection = cityFeatureCollection(rows, "opportunity");
    expect(collection.features).toHaveLength(2);
    const big = collection.features.find((f) => f.properties.geoId === "US/big");
    const small = collection.features.find(
      (f) => f.properties.geoId === "US/small",
    );
    expect(big?.properties.radius).toBe(CITY_MAX_RADIUS);
    // sqrt(100/400) = 0.5 of the radius range above the minimum.
    expect(small?.properties.radius).toBe(
      CITY_MIN_RADIUS + (CITY_MAX_RADIUS - CITY_MIN_RADIUS) * 0.5,
    );
    expect(big?.geometry.coordinates).toEqual([-100, 40]);
  });

  it("marks low-confidence cities as hollow rings, never color alone", () => {
    const collection = cityFeatureCollection(
      [
        cityRow({
          geoId: "US/faint",
          name: "Faint",
          longitude: -80,
          latitude: 30,
          confidenceScore: 20,
        }),
      ],
      "opportunity",
    );
    const feature = collection.features[0];
    expect(feature.properties.lowConfidence).toBe(true);
    expect(feature.properties.fillOpacity).toBeLessThan(0.5);
    expect(feature.properties.strokeWidth).toBeGreaterThan(1);
  });
});

describe("countryPointFeatureCollection", () => {
  it("renders point markers only for ranked countries without polygons", () => {
    const rows = [
      syntheticCountryRows[0], // US — has a 110m polygon, no marker
      {
        ...syntheticCountryRows[1],
        geoId: "SG",
        countryCode: "SG",
        name: "Singapore",
      },
    ];
    const collection = countryPointFeatureCollection(rows, "opportunity");
    expect(collection.features).toHaveLength(1);
    const feature = collection.features[0];
    expect(feature.properties.geoId).toBe("SG");
    expect(feature.properties.radius).toBe(MICROSTATE_RADIUS);
    expect(feature.geometry.coordinates).toEqual(MICROSTATE_CENTROIDS.SG);
  });

  it("ignores city rows entirely", () => {
    const collection = countryPointFeatureCollection(
      [cityRow({ geoId: "SG-somewhere", name: "Somewhere", countryCode: "SG" })],
      "opportunity",
    );
    expect(collection.features).toHaveLength(0);
  });
});
