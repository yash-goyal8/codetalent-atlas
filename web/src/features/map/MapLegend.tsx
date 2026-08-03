import { cn } from "../../lib/cn";
import type { ScoreLayer } from "../../lib/urlstate";
import type { GeoLevel } from "../../types/data";
import { NO_DATA_FILL, SCORE_LAYER_LABELS, SEQUENTIAL_RAMP } from "./scale";

export interface MapLegendProps {
  layer: ScoreLayer;
  level: GeoLevel;
  className?: string;
}

/**
 * Always-visible map legend: the sequential 0-100 ramp for the active
 * score layer plus the two non-color encodings (dashed/faded = low
 * confidence, near-transparent = no data). Real text, not color alone
 * (spec 19, accessibility).
 */
export function MapLegend({ layer, level, className }: MapLegendProps) {
  const gradient = `linear-gradient(to right, ${SEQUENTIAL_RAMP.join(", ")})`;
  return (
    <div
      className={cn(
        "max-w-56 rounded-md border border-border bg-surface-1/90 px-3 py-2 text-[11px] leading-4 text-secondary backdrop-blur",
        className,
      )}
    >
      <p className="font-medium text-primary">
        {SCORE_LAYER_LABELS[layer]} score
      </p>
      <div className="mt-1 flex items-center gap-1.5">
        <span className="score-value">0</span>
        <span
          aria-hidden="true"
          className="h-1.5 w-24 rounded-full"
          style={{ background: gradient }}
        />
        <span className="score-value">100</span>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="inline-block size-3 shrink-0 rounded-[3px] border border-dashed border-primary/60"
          style={{ backgroundColor: "rgba(109, 139, 255, 0.25)" }}
        />
        <span>Low confidence: faded, dashed border</span>
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="inline-block size-3 shrink-0 rounded-[3px] border border-white/15"
          style={{ backgroundColor: NO_DATA_FILL }}
        />
        <span>No data in current view</span>
      </div>
      {level === "city" ? (
        <div className="mt-1 flex items-center gap-1.5">
          <span aria-hidden="true" className="flex items-end gap-0.5">
            <span className="inline-block size-1.5 rounded-full bg-accent/80" />
            <span className="inline-block size-3 rounded-full bg-accent/80" />
          </span>
          <span>City points sized by observable experts</span>
        </div>
      ) : null}
    </div>
  );
}
