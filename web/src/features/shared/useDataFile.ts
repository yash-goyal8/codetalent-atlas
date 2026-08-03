import { useEffect, useState } from "react";
import type { DataResult } from "../../lib/data";

/**
 * Hook-level state for one static data file: the three `DataResult`
 * states plus `loading` while the fetch is in flight. Each state maps
 * onto a designed UI treatment (skeleton / content / awaiting-pipeline
 * empty state / load-failure state) per spec section 19.
 */
export type DataState<T> = { status: "loading" } | DataResult<T>;

/**
 * Load one static data file on mount (and whenever `load` changes
 * identity). Pass a module-stable loader (e.g. `loadSummary`) or wrap a
 * parameterized one in `useCallback`.
 */
export function useDataFile<T>(load: () => Promise<DataResult<T>>): DataState<T> {
  const [state, setState] = useState<DataState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    void load().then((result) => {
      if (!cancelled) {
        setState(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  return state;
}
