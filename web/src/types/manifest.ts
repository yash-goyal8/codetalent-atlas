/**
 * Static data contract for `web/public/data/manifest.json`, per spec
 * section 20. The manifest is written by the publish pipeline
 * (Milestone E) and consumed read-only by the frontend.
 */

/** Inclusive event-collection window of the dataset, ISO dates. */
export interface DatasetWindow {
  start: string;
  end: string;
}

/**
 * Logical file keys mapped to paths relative to `web/public/data/`,
 * e.g. `summary` -> "summary.json",
 * `countryRankings` -> "rankings/cloud_devops/countries.json".
 */
export type ManifestFiles = Record<string, string>;

export interface Manifest {
  /** e.g. "2026.08.01-pilot.1" */
  datasetVersion: string;
  /** ISO-8601 timestamp of pipeline publish. */
  generatedAt: string;
  window: DatasetWindow;
  /** Domain ids covered by the dataset, e.g. ["cloud_devops"]. */
  domains: string[];
  files: ManifestFiles;
  /** e.g. "1.0.0" */
  methodologyVersion: string;
}
