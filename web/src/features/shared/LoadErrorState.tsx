import { TriangleAlert } from "lucide-react";
import { cn } from "../../lib/cn";

export const LOAD_ERROR_MESSAGE =
  "This data file failed to load. Reload the page to retry.";

interface LoadErrorStateProps {
  /** Technical detail (HTTP status, parse error) shown under the message. */
  detail?: string;
  className?: string;
}

/**
 * Designed data-file load-failure state (spec section 19, empty/error
 * states). Distinct from `EmptyState`, which means the pipeline has not
 * published the file yet; this one means the fetch or parse failed.
 */
export function LoadErrorState({ detail, className }: LoadErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed border-warning/40 bg-surface-1 px-6 py-10 text-center",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="flex size-10 items-center justify-center rounded-full border border-warning/30 bg-warning/10"
      >
        <TriangleAlert className="size-5 text-warning" />
      </span>
      <p className="max-w-md text-sm font-medium text-primary">
        {LOAD_ERROR_MESSAGE}
      </p>
      {detail ? (
        <p className="max-w-md text-xs leading-5 text-secondary">{detail}</p>
      ) : null}
    </div>
  );
}
