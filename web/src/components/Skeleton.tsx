import { cn } from "../lib/cn";

export interface SkeletonProps {
  className?: string;
}

/**
 * Loading placeholder block. The pulse animation is suppressed under
 * `prefers-reduced-motion` (both via the `motion-reduce:` variant and
 * the global reduced-motion CSS). Hidden from assistive tech — pair
 * with a live-region or status text at the container level.
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse rounded-md bg-surface-2 motion-reduce:animate-none",
        className,
      )}
    />
  );
}
