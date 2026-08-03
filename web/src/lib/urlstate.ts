/**
 * Typed URL search-param state (spec section 20, state management).
 * Filters live in the URL so every analytical view is shareable and
 * survives reload. Defaults are omitted from the URL to keep it clean;
 * unknown params are preserved so this module composes with anything
 * else that uses the query string.
 */

import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { GeoLevel, RecommendationTier } from "../types/rankings";
import { DEFAULT_DOMAIN_ID } from "./data";

/** Map/rail score layer toggles (spec 19.2). */
export type ScoreLayer =
  | "opportunity"
  | "supply"
  | "quality"
  | "momentum"
  | "confidence";

export interface UrlState {
  domain: string;
  /** Subdomain filter, null = all subdomains. */
  subdomain: string | null;
  level: GeoLevel;
  layer: ScoreLayer;
  /** Minimum confidence score filter, 0-100. 0 = no filter. */
  minConfidence: number;
  /** Recommendation-tier filter, null = all tiers. */
  tier: RecommendationTier | null;
  /** Selected geoIds (compare/explorer), max MAX_SELECTED. */
  selected: string[];
  /** Free-text location search. */
  search: string;
}

export const MAX_SELECTED = 4;

export const DEFAULT_URL_STATE: UrlState = {
  domain: DEFAULT_DOMAIN_ID,
  subdomain: null,
  level: "country",
  layer: "opportunity",
  minConfidence: 0,
  tier: null,
  selected: [],
  search: "",
};

/** Query-string keys managed by this module. */
export const URL_STATE_KEYS = [
  "domain",
  "subdomain",
  "level",
  "layer",
  "minConfidence",
  "tier",
  "selected",
  "search",
] as const;

const GEO_LEVELS: readonly GeoLevel[] = ["country", "city"];
const SCORE_LAYERS: readonly ScoreLayer[] = [
  "opportunity",
  "supply",
  "quality",
  "momentum",
  "confidence",
];
const TIERS: readonly RecommendationTier[] = [
  "priority",
  "promising",
  "monitor",
  "insufficient_data",
];

function parseEnum<T extends string>(
  value: string | null,
  allowed: readonly T[],
  fallback: T,
): T {
  return value !== null && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

function clampConfidence(raw: string | null): number {
  if (raw === null) return DEFAULT_URL_STATE.minConfidence;
  const parsed = Number.parseFloat(raw);
  if (!Number.isFinite(parsed)) return DEFAULT_URL_STATE.minConfidence;
  return Math.min(100, Math.max(0, parsed));
}

/** Dedupe (order-preserving), drop empties, cap at MAX_SELECTED. */
export function normalizeSelected(geoIds: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of geoIds) {
    const trimmed = id.trim();
    if (trimmed === "" || seen.has(trimmed)) continue;
    seen.add(trimmed);
    out.push(trimmed);
    if (out.length === MAX_SELECTED) break;
  }
  return out;
}

/** Read a validated UrlState out of URL search params. Never throws. */
export function parseUrlState(params: URLSearchParams): UrlState {
  const subdomain = params.get("subdomain");
  const tierRaw = params.get("tier");
  const selectedRaw = params.get("selected");
  return {
    domain: params.get("domain") ?? DEFAULT_URL_STATE.domain,
    subdomain: subdomain === null || subdomain === "" ? null : subdomain,
    level: parseEnum(params.get("level"), GEO_LEVELS, DEFAULT_URL_STATE.level),
    layer: parseEnum(params.get("layer"), SCORE_LAYERS, DEFAULT_URL_STATE.layer),
    minConfidence: clampConfidence(params.get("minConfidence")),
    tier:
      tierRaw !== null && (TIERS as readonly string[]).includes(tierRaw)
        ? (tierRaw as RecommendationTier)
        : null,
    selected: selectedRaw === null ? [] : normalizeSelected(selectedRaw.split(",")),
    search: params.get("search") ?? "",
  };
}

/**
 * Write a UrlState into search params. Defaults are omitted; params not
 * managed by this module (already present in `base`) are preserved.
 */
export function serializeUrlState(
  state: UrlState,
  base?: URLSearchParams,
): URLSearchParams {
  const params = new URLSearchParams(base);
  for (const key of URL_STATE_KEYS) {
    params.delete(key);
  }
  if (state.domain !== DEFAULT_URL_STATE.domain) {
    params.set("domain", state.domain);
  }
  if (state.subdomain !== null && state.subdomain !== "") {
    params.set("subdomain", state.subdomain);
  }
  if (state.level !== DEFAULT_URL_STATE.level) {
    params.set("level", state.level);
  }
  if (state.layer !== DEFAULT_URL_STATE.layer) {
    params.set("layer", state.layer);
  }
  if (state.minConfidence !== DEFAULT_URL_STATE.minConfidence) {
    params.set("minConfidence", String(state.minConfidence));
  }
  if (state.tier !== null) {
    params.set("tier", state.tier);
  }
  const selected = normalizeSelected(state.selected);
  if (selected.length > 0) {
    params.set("selected", selected.join(","));
  }
  if (state.search !== "") {
    params.set("search", state.search);
  }
  return params;
}

/**
 * Read/patch the URL state. The setter merges a partial patch into the
 * current state and replaces the history entry (filter changes should
 * not pollute the back stack).
 */
export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseUrlState(params), [params]);

  const update = useCallback(
    (patch: Partial<UrlState>) => {
      setParams(
        (prev) => serializeUrlState({ ...parseUrlState(prev), ...patch }, prev),
        { replace: true },
      );
    },
    [setParams],
  );

  return [state, update];
}
