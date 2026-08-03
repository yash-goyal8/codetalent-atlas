import { formatCount } from "../../lib/format";
import type { FunnelStage } from "../../types/data";

/**
 * Data funnel visualization (spec 19.6) from validation.json: centered
 * bars whose widths are proportional to stage counts. Counts are always
 * printed, so the numbers never depend on bar width alone.
 */
export function FunnelChart({ funnel }: { funnel: FunnelStage[] }) {
  const max = Math.max(...funnel.map((stage) => stage.count), 1);
  return (
    <ol aria-label="Data funnel stages with counts" className="list-none space-y-2">
      {funnel.map((stage) => {
        const width = Math.max((stage.count / max) * 100, 4);
        return (
          <li key={stage.stage} className="flex flex-col items-center gap-1">
            <div className="flex w-full items-baseline justify-between gap-4 text-xs">
              <span className="text-secondary">{stage.stage}</span>
              <span className="score-value font-semibold text-primary">
                {formatCount(stage.count)}
              </span>
            </div>
            <div
              aria-hidden="true"
              className="h-5 rounded-md bg-accent/25 ring-1 ring-inset ring-accent/40"
              style={{ width: `${width}%` }}
            />
          </li>
        );
      })}
    </ol>
  );
}
