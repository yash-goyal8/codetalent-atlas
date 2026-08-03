import type { Manifest } from "../types/manifest";
import type {
  CompareFile,
  CoverageFile,
  GeoLevel,
  LocationDetail,
  RankingsFile,
  RecommendationsFile,
  Summary,
  ValidationFile,
} from "../types/data";
import { registerSubdomainNames } from "./subdomains";

export const MANIFEST_URL = "/data/manifest.json";

/** Pilot domain id; every loader defaults to it until expansion domains ship. */
export const DEFAULT_DOMAIN_ID = "cloud_devops";

/**
 * Discriminated result so callers can branch to a designed empty state
 * instead of throwing: the manifest is legitimately absent until the
 * first pipeline run publishes `web/public/data/manifest.json`.
 */
export type ManifestResult =
  | { kind: "ok"; manifest: Manifest }
  | { kind: "missing"; reason: string };

/** Fetch and parse the dataset manifest. Never throws. */
export async function loadManifest(): Promise<ManifestResult> {
  try {
    const response = await fetch(MANIFEST_URL);
    if (!response.ok) {
      return { kind: "missing", reason: `HTTP ${response.status}` };
    }
    const manifest = (await response.json()) as Manifest;
    return { kind: "ok", manifest };
  } catch (error) {
    return {
      kind: "missing",
      reason: error instanceof Error ? error.message : "unknown fetch error",
    };
  }
}

/**
 * Result of loading one static data file. Three states map onto the three
 * designed UI states (spec 19): `ok` renders data, `missing` renders the
 * awaiting-pipeline empty state (the file simply is not published yet),
 * `error` renders the load-failure state (network/server/parse problem).
 */
export type DataResult<T> =
  | { status: "ok"; data: T }
  | { status: "missing" }
  | { status: "error"; message: string };

/**
 * In-module cache, one entry per path. Only `ok` results stay cached so a
 * transient network error can be retried; `missing` is re-checked cheaply
 * (static hosting answers 404 fast) and stays correct if a dataset is
 * published mid-session.
 */
const cache = new Map<string, Promise<DataResult<unknown>>>();

/** Test/HMR helper: drop every cached data file. */
export function clearDataCache(): void {
  cache.clear();
}

async function fetchJsonUncached<T>(path: string): Promise<DataResult<T>> {
  try {
    const response = await fetch(path);
    if (response.status === 404) {
      return { status: "missing" };
    }
    if (!response.ok) {
      return { status: "error", message: `HTTP ${response.status}` };
    }
    /*
     * SPA-fallback hosts (vite preview, Cloudflare Pages without a
     * 404.html) answer a missing .json path with 200 + index.html. That
     * is the file being absent, not a load failure — treat it as the
     * designed "missing" state instead of the alarming error state.
     */
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("text/html")) {
      return { status: "missing" };
    }
    try {
      const data = (await response.json()) as T;
      return { status: "ok", data };
    } catch {
      return { status: "error", message: `Invalid JSON in ${path}` };
    }
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : "unknown fetch error",
    };
  }
}

/**
 * Fetch and parse one static JSON file under the site root. Never throws;
 * concurrent calls for the same path share one request, and successful
 * results are cached for the session.
 */
export function fetchJson<T>(path: string): Promise<DataResult<T>> {
  const cached = cache.get(path);
  if (cached) {
    return cached as Promise<DataResult<T>>;
  }
  const pending = fetchJsonUncached<T>(path).then((result) => {
    if (result.status !== "ok") {
      cache.delete(path);
    }
    return result;
  });
  cache.set(path, pending);
  return pending as Promise<DataResult<T>>;
}

export function loadSummary(): Promise<DataResult<Summary>> {
  return fetchJson<Summary>("/data/summary.json").then((result) => {
    if (result.status === "ok") {
      // Pipeline-published display names feed the shared subdomain labels.
      registerSubdomainNames(result.data.subdomainHubs);
    }
    return result;
  });
}

export function loadRankings(
  level: GeoLevel,
  domainId: string = DEFAULT_DOMAIN_ID,
): Promise<DataResult<RankingsFile>> {
  const file = level === "country" ? "countries" : "cities";
  return fetchJson<RankingsFile>(`/data/rankings/${domainId}/${file}.json`);
}

/**
 * City geoIds start with an ISO alpha-2 country code followed by a
 * separator and a slug. The pipeline emits "CC-city-slug"
 * ("GB-london"); the earlier draft contract used "CC/city-slug"
 * ("US/san-francisco") — both are recognized. Bare two-letter ids are
 * countries.
 */
const CITY_GEO_ID_PATTERN = /^[A-Za-z]{2}[-/]./;

/**
 * Map a geoId to its detail-file path. Country geoIds are bare ISO
 * alpha-2 codes ("DE" -> locations/countries/DE.json); city geoIds
 * ("GB-london", legacy "US/san-francisco") map to
 * locations/cities/<lowercased, "/"->"-">.json ("gb-london.json").
 */
export function locationDetailPath(geoId: string): string {
  if (CITY_GEO_ID_PATTERN.test(geoId)) {
    const slug = geoId.toLowerCase().replace(/\//g, "-");
    return `/data/locations/cities/${slug}.json`;
  }
  return `/data/locations/countries/${geoId.toUpperCase()}.json`;
}

export function loadLocationDetail(
  geoId: string,
): Promise<DataResult<LocationDetail>> {
  return fetchJson<LocationDetail>(locationDetailPath(geoId)).then((result) => {
    if (result.status === "ok") {
      registerSubdomainNames(result.data.subdomainMix);
    }
    return result;
  });
}

export function loadCompare(
  domainId: string = DEFAULT_DOMAIN_ID,
): Promise<DataResult<CompareFile>> {
  return fetchJson<CompareFile>(`/data/compare/${domainId}.json`);
}

export function loadValidation(): Promise<DataResult<ValidationFile>> {
  return fetchJson<ValidationFile>("/data/methodology/validation.json");
}

export function loadCoverage(): Promise<DataResult<CoverageFile>> {
  return fetchJson<CoverageFile>("/data/methodology/coverage.json");
}

export function loadRecommendations(
  domainId: string = DEFAULT_DOMAIN_ID,
): Promise<DataResult<RecommendationsFile>> {
  return fetchJson<RecommendationsFile>(`/data/recommendations/${domainId}.json`);
}
