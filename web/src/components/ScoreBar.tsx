import { cn } from "../lib/cn";
import { formatScore } from "../lib/format";

export interface ScoreBarProps {
  /** Metric name, e.g. "Expert supply". */
  label: string;
  /** Score on the canonical 0-100 scale. */
  value: number;
  /** Fill color utility class; value text keeps meaning without it. */
  colorClass?: string;
  className?: string;
}

/**
 * Horizontal 0-100 score bar. The numeric value is always printed next
 * to the bar (tabular numerals), so color/length never carry meaning
 * alone (spec 19, accessibility).
 */
export function ScoreBar({ label, value, colorClass, className }: ScoreBarProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className="w-44 shrink-0 truncate text-xs text-secondary">
        {label}
      </span>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        aria-valuetext={formatScore(value)}
        className="h-1.5 min-w-16 flex-1 overflow-hidden rounded-full bg-surface-2"
      >
        <div
          className={cn("h-full rounded-full", colorClass ?? "bg-accent")}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="score-value w-10 shrink-0 text-right text-xs font-medium text-primary">
        {formatScore(value)}
      </span>
    </div>
  );
}
