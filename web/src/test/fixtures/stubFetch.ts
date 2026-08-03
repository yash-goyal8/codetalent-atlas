/**
 * SYNTHETIC TEST INFRASTRUCTURE — unit tests only.
 *
 * Stubs `globalThis.fetch` so routes exercise the real `lib/data`
 * loaders against the synthetic fixture dataset without any network.
 * Never imported by product code; nothing here reaches `web/public`.
 */

import { vi } from "vitest";
import type { LocationDetail } from "../../types/data";
import {
  syntheticCompare,
  syntheticCountryRankings,
  syntheticCityRows,
  syntheticCityRankings,
  syntheticCountryRows,
  syntheticCoverage,
  syntheticLocationDetail,
  syntheticManifest,
  syntheticRecommendations,
  syntheticSummary,
  syntheticValidation,
} from "./dataset";

/**
 * Synthetic detail file whose ranking row (IN) carries a provisional
 * momentum flag, for testing the provisional labeling paths.
 */
export const syntheticProvisionalDetail: LocationDetail = {
  ...syntheticLocationDetail,
  ranking: syntheticCountryRows[2],
};

/**
 * Synthetic city detail file (Testville), for the city-geoId path.
 */
export const syntheticCityDetail: LocationDetail = {
  ...syntheticLocationDetail,
  ranking: syntheticCityRows[0],
};

/** Synthetic optional sensitivity file (spec 19.6, render-only-if-present). */
export const syntheticSensitivity = {
  summary: "Synthetic sensitivity summary — fixture text only.",
  scenarios: [
    {
      name: "Synthetic scenario A",
      result: "Synthetic scenario result — fixture text only.",
    },
  ],
};

/** Sentinel: serve an HTTP 500 for this path (drives the error state). */
export const SERVER_ERROR = Symbol("SERVER_ERROR");

export type StubbedFiles = Record<string, unknown | typeof SERVER_ERROR>;

/**
 * Stub fetch with a path -> JSON body map. Paths absent from the map
 * return 404, which `lib/data` maps to the `missing` (awaiting-pipeline)
 * state. Pass `SERVER_ERROR` as a body to return HTTP 500 instead.
 * Callers must `vi.unstubAllGlobals()` and `clearDataCache()` after.
 */
export function stubDataFetch(files: StubbedFiles = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    if (path in files) {
      const body = files[path];
      if (body === SERVER_ERROR) {
        return new Response("synthetic server error", { status: 500 });
      }
      return new Response(JSON.stringify(body), {
        headers: { "Content-Type": "application/json" },
      });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/**
 * The complete synthetic dataset keyed by public path — the "full data"
 * state for route tests. Spread and override/delete entries to build
 * partial-data states.
 */
export function syntheticFiles(): StubbedFiles {
  return {
    "/data/manifest.json": syntheticManifest,
    "/data/summary.json": syntheticSummary,
    "/data/rankings/cloud_devops/countries.json": syntheticCountryRankings,
    "/data/rankings/cloud_devops/cities.json": syntheticCityRankings,
    "/data/locations/countries/US.json": syntheticLocationDetail,
    "/data/compare/cloud_devops.json": syntheticCompare,
    "/data/methodology/validation.json": syntheticValidation,
    "/data/methodology/coverage.json": syntheticCoverage,
    "/data/recommendations/cloud_devops.json": syntheticRecommendations,
  };
}

/**
 * Guard for the "no username anywhere" requirement (spec 20, E2E flow
 * 8): the fixture contains no usernames, so any handle-like string or
 * GitHub profile URL in rendered output was introduced by the UI.
 */
export function expectNoUsernameArtifacts(text: string | null): void {
  const content = text ?? "";
  if (/@[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}/.test(content)) {
    throw new Error(
      `Rendered output contains a handle-like "@" string: ${content.match(/@\S+/)?.[0] ?? ""}`,
    );
  }
  if (/github\.com\//i.test(content)) {
    throw new Error("Rendered output contains a github.com profile URL");
  }
}
