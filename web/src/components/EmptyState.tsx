import { DatabaseZap } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../lib/cn";

export const AWAITING_DATASET_MESSAGE =
  "Awaiting first dataset — the Cloud and DevOps pilot pipeline has not been run yet";

interface EmptyStateProps {
  /** Extra route-specific context rendered under the shared message. */
  detail?: ReactNode;
  className?: string;
}

/**
 * Designed empty state (spec section 19, empty/error states) shown on
 * every route until the pilot pipeline publishes its first dataset.
 */
export function EmptyState({ detail, className }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center gap-4 rounded-lg border border-dashed border-white/15 bg-surface-1 px-6 py-14 text-center",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full border border-accent/30 bg-accent/10"
      >
        <DatabaseZap className="size-6 text-accent" />
      </span>
      <p className="max-w-md text-sm font-medium text-primary">
        {AWAITING_DATASET_MESSAGE}
      </p>
      {detail ? (
        <p className="max-w-md text-xs leading-5 text-secondary">{detail}</p>
      ) : null}
    </div>
  );
}
