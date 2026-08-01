import { useEffect, useState } from "react";
import { loadManifest, type ManifestResult } from "../lib/data";

export type ManifestState = { kind: "loading" } | ManifestResult;

/** Load the dataset manifest once on mount; resolves to ok or missing. */
export function useManifest(): ManifestState {
  const [state, setState] = useState<ManifestState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void loadManifest().then((result) => {
      if (!cancelled) {
        setState(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
