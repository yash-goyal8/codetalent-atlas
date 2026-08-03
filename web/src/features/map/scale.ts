/**
 * Choropleth color scale and MapLibre expression builders for the Atlas
 * map (spec 19.2/19.3, dataviz method).
 *
 * The sequential ramp is derived from the accent token #6D8BFF: one hue,
 * five perceptually ordered lightness steps from dim to light on the
 * dark basemap, so higher scores read lighter/more prominent — never a
 * rainbow. Validated with the dataviz ordinal-ramp checks: monotone
 * OKLCH lightness, adjacent dL >= 0.06, dark end >= 2:1 contrast against
 * the #070A12 background, hue spread 2 degrees.
 *
 * Confidence is never encoded by color alone: low-confidence geographies
 * additionally get reduced fill opacity plus a dashed border (countries)
 * or a hollow ring (cities), and confidence is always spelled out in
 * tooltip and table text.
 */

import type { ExpressionSpecification, FilterSpecification } from "maplibre-gl";
import { confidenceLevel } from "../../lib/format";
import type { ScoreLayer } from "../../lib/urlstate";
import type { GeographicRankingRow } from "../../types/data";

// ---------------------------------------------------------------------------
// Score layers
// ---------------------------------------------------------------------------

/** Human labels for the five score layers (spec 19.2 layer toggle). */
export const SCORE_LAYER_LABELS: Record<ScoreLayer, string> = {
  opportunity: "Opportunity",
  supply: "Expert supply",
  quality: "Expert quality",
  momentum: "Momentum",
  confidence: "Confidence",
};

const SCORE_LAYER_FIELDS: Record<
  ScoreLayer,
  | "opportunityScore"
  | "expertSupplyScore"
  | "expertQualityScore"
  | "momentumScore"
  | "confidenceScore"
> = {
  opportunity: "opportunityScore",
  supply: "expertSupplyScore",
  quality: "expertQualityScore",
  momentum: "momentumScore",
  confidence: "confidenceScore",
};

/** The 0-100 score a row contributes to the active map layer. */
export function scoreForLayer(
  row: GeographicRankingRow,
  layer: ScoreLayer,
): number {
  return row[SCORE_LAYER_FIELDS[layer]];
}

/**
 * Presentation-only label for a subdomain id: "ci_cd" -> "CI CD",
 * "cloud_platforms" -> "Cloud Platforms". Display names published by the
 * pipeline (summary.subdomainHubs, subdomainMix) take precedence where
 * available; this is the generic fallback for bare ids in ranking rows.
 */
export function subdomainLabel(id: string): string {
  return id
    .split(/[_-]+/)
    .filter((word) => word.length > 0)
    .map((word) =>
      word.length <= 3
        ? word.toUpperCase()
        : word[0].toUpperCase() + word.slice(1),
    )
    .join(" ");
}

// ---------------------------------------------------------------------------
// Sequential color ramp
// ---------------------------------------------------------------------------

/**
 * Accent-derived sequential ramp, dark (score 0) to light (score 100).
 * Step 4 is the accent token itself. See module header for validation.
 */
export const SEQUENTIAL_RAMP = [
  "#33427b",
  "#4459a2",
  "#5872cc",
  "#6d8bff",
  "#b2c7ff",
] as const;

/** Near-transparent fill for countries with no data in the current view. */
export const NO_DATA_FILL = "rgba(244, 247, 251, 0.04)";
/** Subtle border drawn on every country polygon. */
export const SUBTLE_BORDER = "rgba(244, 247, 251, 0.12)";
/** Fill opacity for geographies with data at normal confidence. */
export const DATA_FILL_OPACITY = 0.88;
/** Reduced fill opacity for low-confidence geographies (plus dashed border). */
export const LOW_CONFIDENCE_FILL_OPACITY = 0.45;

function hexChannel(hex: string, index: number): number {
  return Number.parseInt(hex.slice(1 + index * 2, 3 + index * 2), 16);
}

/**
 * Map a 0-100 score onto the sequential ramp with piecewise-linear
 * interpolation between the five validated stops. Non-finite input
 * clamps to the dark end.
 */
export function colorForScore(score: number): string {
  const clamped = Number.isFinite(score)
    ? Math.min(100, Math.max(0, score))
    : 0;
  const position = (clamped / 100) * (SEQUENTIAL_RAMP.length - 1);
  const lowIndex = Math.min(Math.floor(position), SEQUENTIAL_RAMP.length - 2);
  const t = position - lowIndex;
  const low = SEQUENTIAL_RAMP[lowIndex];
  const high = SEQUENTIAL_RAMP[lowIndex + 1];
  const channels = [0, 1, 2].map((i) => {
    const mixed = Math.round(
      hexChannel(low, i) + (hexChannel(high, i) - hexChannel(low, i)) * t,
    );
    return mixed.toString(16).padStart(2, "0");
  });
  return `#${channels.join("")}`;
}

// ---------------------------------------------------------------------------
// Confidence treatment
// ---------------------------------------------------------------------------

/**
 * True when a geography must carry the low-confidence treatment
 * (reduced opacity + dashed border / hollow ring, spec 19.2): either the
 * confidence score buckets as "low" or the tier is insufficient_data.
 */
export function isLowConfidence(row: GeographicRankingRow): boolean {
  return (
    row.recommendationTier === "insufficient_data" ||
    confidenceLevel(row.confidenceScore) === "low"
  );
}

// ---------------------------------------------------------------------------
// MapLibre expressions (country choropleth)
// ---------------------------------------------------------------------------

/** Sentinel that matches no feature id. */
const NO_MATCH = "__none__";

/** Filter that hides a layer until a real id is set. */
export const NONE_FILTER = [
  "==",
  ["id"],
  NO_MATCH,
] as unknown as FilterSpecification;

function uniqueCountryRows(
  rows: readonly GeographicRankingRow[],
): GeographicRankingRow[] {
  const byGeo = new Map<string, GeographicRankingRow>();
  for (const row of rows) {
    if (row.geoLevel === "country" && !byGeo.has(row.geoId)) {
      byGeo.set(row.geoId, row);
    }
  }
  return [...byGeo.values()];
}

/**
 * `fill-color` for the country choropleth: a match on the feature id
 * (ISO alpha-2, the geoId) mapping each ranked country to its ramp
 * color for the active layer; everything else near-transparent.
 */
export function countryFillColor(
  rows: readonly GeographicRankingRow[],
  layer: ScoreLayer,
): ExpressionSpecification | string {
  const countryRows = uniqueCountryRows(rows);
  if (countryRows.length === 0) return NO_DATA_FILL;
  const expression: unknown[] = ["match", ["id"]];
  for (const row of countryRows) {
    expression.push(row.geoId, colorForScore(scoreForLayer(row, layer)));
  }
  expression.push(NO_DATA_FILL);
  return expression as unknown as ExpressionSpecification;
}

/**
 * `fill-opacity` companion: low-confidence countries render faded (one
 * of the two non-color confidence encodings), ranked countries at the
 * standard opacity, no-data countries fully (their fill is transparent).
 */
export function countryFillOpacity(
  rows: readonly GeographicRankingRow[],
): ExpressionSpecification | number {
  const countryRows = uniqueCountryRows(rows);
  if (countryRows.length === 0) return 1;
  const expression: unknown[] = ["match", ["id"]];
  for (const row of countryRows) {
    expression.push(
      row.geoId,
      isLowConfidence(row) ? LOW_CONFIDENCE_FILL_OPACITY : DATA_FILL_OPACITY,
    );
  }
  expression.push(1);
  return expression as unknown as ExpressionSpecification;
}

/** Filter selecting the low-confidence countries for the dashed-border layer. */
export function lowConfidenceCountryFilter(
  rows: readonly GeographicRankingRow[],
): FilterSpecification {
  const ids = uniqueCountryRows(rows)
    .filter(isLowConfidence)
    .map((row) => row.geoId);
  return [
    "in",
    ["id"],
    ["literal", ids],
  ] as unknown as FilterSpecification;
}

/** Filter highlighting one country by geoId (hover/selection outline). */
export function countryIdFilter(geoId: string | null): FilterSpecification {
  return ["==", ["id"], geoId ?? NO_MATCH] as unknown as FilterSpecification;
}

/** Filter highlighting one (unclustered) city point by geoId. */
export function cityIdFilter(geoId: string | null): FilterSpecification {
  return [
    "all",
    ["!", ["has", "point_count"]],
    ["==", ["get", "geoId"], geoId ?? NO_MATCH],
  ] as unknown as FilterSpecification;
}

// ---------------------------------------------------------------------------
// City points
// ---------------------------------------------------------------------------

/**
 * Optional centroid fields for city rows ("local city centroid
 * coordinates from normalized aggregate output", spec 20 map
 * requirements). Not yet part of the published rankings contract — read
 * defensively; cities without coordinates simply render no point.
 */
export interface CityCoordinateFields {
  longitude?: number;
  latitude?: number;
  /** [longitude, latitude] */
  centroid?: readonly number[];
}

/** Extract [lon, lat] from a city row if the pipeline emitted coordinates. */
export function cityCoordinates(
  row: GeographicRankingRow,
): [number, number] | null {
  const fields = row as GeographicRankingRow & CityCoordinateFields;
  if (
    typeof fields.longitude === "number" &&
    Number.isFinite(fields.longitude) &&
    typeof fields.latitude === "number" &&
    Number.isFinite(fields.latitude)
  ) {
    return [fields.longitude, fields.latitude];
  }
  const centroid = fields.centroid;
  if (
    Array.isArray(centroid) &&
    centroid.length === 2 &&
    typeof centroid[0] === "number" &&
    Number.isFinite(centroid[0]) &&
    typeof centroid[1] === "number" &&
    Number.isFinite(centroid[1])
  ) {
    return [centroid[0], centroid[1]];
  }
  return null;
}

export const CITY_MIN_RADIUS = 4;
export const CITY_MAX_RADIUS = 18;

export interface CityPointProperties {
  geoId: string;
  name: string;
  /** Circle radius in px, sized by observable expert count (sqrt scale). */
  radius: number;
  /** Ramp color for the active score layer. */
  color: string;
  /** Low-confidence cities render as hollow rings (see module header). */
  fillOpacity: number;
  strokeWidth: number;
  lowConfidence: boolean;
}

export interface CityPointFeature {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: CityPointProperties;
}

export interface CityPointCollection {
  type: "FeatureCollection";
  features: CityPointFeature[];
}

export const EMPTY_CITY_COLLECTION: CityPointCollection = {
  type: "FeatureCollection",
  features: [],
};

/**
 * Build the city circle-layer source: one point per city row that
 * carries coordinates, sized by observable expert count on a square-root
 * scale relative to the largest visible pool.
 */
export function cityFeatureCollection(
  rows: readonly GeographicRankingRow[],
  layer: ScoreLayer,
): CityPointCollection {
  const located: Array<{
    row: GeographicRankingRow;
    coordinates: [number, number];
  }> = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (row.geoLevel !== "city" || seen.has(row.geoId)) continue;
    const coordinates = cityCoordinates(row);
    if (!coordinates) continue;
    seen.add(row.geoId);
    located.push({ row, coordinates });
  }
  const maxCount = located.reduce(
    (max, entry) => Math.max(max, entry.row.observableExpertCount),
    1,
  );
  return {
    type: "FeatureCollection",
    features: located.map(({ row, coordinates }) => {
      const lowConfidence = isLowConfidence(row);
      const share = Math.max(0, row.observableExpertCount) / maxCount;
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates },
        properties: {
          geoId: row.geoId,
          name: row.name,
          radius:
            CITY_MIN_RADIUS +
            (CITY_MAX_RADIUS - CITY_MIN_RADIUS) * Math.sqrt(share),
          color: colorForScore(scoreForLayer(row, layer)),
          fillOpacity: lowConfidence ? 0.25 : 0.85,
          strokeWidth: lowConfidence ? 1.8 : 1,
          lowConfidence,
        },
      };
    }),
  };
}
