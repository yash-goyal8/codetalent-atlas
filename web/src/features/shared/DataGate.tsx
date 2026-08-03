import type { ReactNode } from "react";
import { EmptyState } from "../../components/EmptyState";
import { LoadErrorState } from "./LoadErrorState";
import type { DataState } from "./useDataFile";

interface DataGateProps<T> {
  state: DataState<T>;
  /** Rendered while the file is loading (pass Skeletons). */
  skeleton: ReactNode;
  /** Extra context for the awaiting-pipeline empty state. */
  emptyDetail?: ReactNode;
  /** Override the default EmptyState for the `missing` case. */
  missing?: ReactNode;
  children: (data: T) => ReactNode;
}

/**
 * Branch one data file's state into the three designed UI states
 * (spec section 19): skeleton while loading, awaiting-pipeline empty
 * state when the file is not published, load-failure state on error,
 * and the real content once data is available.
 */
export function DataGate<T>({
  state,
  skeleton,
  emptyDetail,
  missing,
  children,
}: DataGateProps<T>) {
  switch (state.status) {
    case "loading":
      return <div role="status" aria-label="Loading data">{skeleton}</div>;
    case "missing":
      return <>{missing ?? <EmptyState detail={emptyDetail} />}</>;
    case "error":
      return <LoadErrorState detail={state.message} />;
    case "ok":
      return <>{children(state.data)}</>;
  }
}
