import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MICROSTATE_CENTROIDS, microstateCentroid } from "./microstates";

/**
 * Countries the pipeline has ranked that Natural Earth 1:110m omits.
 * These MUST stay covered by the centroid table so "all map geo IDs
 * resolve" (spec 21) holds at country level.
 */
const RANKED_POLYGONLESS = [
  "BM",
  "HK",
  "KY",
  "MO",
  "MT",
  "SG",
  "SH",
  "VA",
  "VI",
];

function polygonIds(): Set<string> {
  const geoPath = resolve(
    dirname(fileURLToPath(import.meta.url)),
    "../../../public/geo/countries.geojson",
  );
  const collection = JSON.parse(readFileSync(geoPath, "utf8")) as {
    features: Array<{ id: string }>;
  };
  return new Set(collection.features.map((feature) => feature.id));
}

describe("MICROSTATE_CENTROIDS", () => {
  it("covers every ranked country missing from the 110m polygon set", () => {
    for (const code of RANKED_POLYGONLESS) {
      expect(MICROSTATE_CENTROIDS[code], code).toBeDefined();
    }
  });

  it("never overlaps the polygon ids in countries.geojson", () => {
    const ids = polygonIds();
    const overlap = Object.keys(MICROSTATE_CENTROIDS).filter((code) =>
      ids.has(code),
    );
    expect(overlap).toEqual([]);
  });

  it("holds plausible [longitude, latitude] pairs", () => {
    for (const [code, [lon, lat]] of Object.entries(MICROSTATE_CENTROIDS)) {
      expect(Math.abs(lon), code).toBeLessThanOrEqual(180);
      expect(Math.abs(lat), code).toBeLessThanOrEqual(90);
    }
  });
});

describe("microstateCentroid", () => {
  it("resolves case-insensitively and returns null for polygon countries", () => {
    expect(microstateCentroid("sg")).toEqual(MICROSTATE_CENTROIDS.SG);
    expect(microstateCentroid("US")).toBeNull();
  });
});
