/**
 * Optional sensitivity-analysis summary (spec 19.6). Not part of the
 * core section 20 contract yet — the pipeline may publish it after the
 * ranking-stability tests (spec 18) run. The section renders ONLY when
 * this file exists; there is no placeholder content to invent.
 */

import { fetchJson, type DataResult } from "../../lib/data";

export interface SensitivityScenario {
  name: string;
  /** Pipeline-written outcome sentence, rendered verbatim. */
  result: string;
}

export interface SensitivityFile {
  summary?: string;
  scenarios?: SensitivityScenario[];
}

export function loadSensitivity(): Promise<DataResult<SensitivityFile>> {
  return fetchJson<SensitivityFile>("/data/methodology/sensitivity.json");
}
