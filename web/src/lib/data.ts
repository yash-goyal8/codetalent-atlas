import type { Manifest } from "../types/manifest";

export const MANIFEST_URL = "/data/manifest.json";

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
