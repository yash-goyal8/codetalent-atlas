import { ArrowRight } from "lucide-react";
import { PIPELINE_STAGES } from "./content";

/**
 * Styled pipeline diagram (spec 19.6) matching the section 6 flow:
 * an ordered list rendered as connected steps, fully semantic.
 */
export function PipelineDiagram() {
  return (
    <ol
      aria-label="Data pipeline stages, in order"
      className="flex list-none flex-wrap items-stretch gap-2"
    >
      {PIPELINE_STAGES.map((stage, index) => (
        <li key={stage.name} className="flex items-center gap-2">
          <div className="flex h-full min-w-44 flex-col justify-center rounded-lg border border-border bg-surface-1 px-4 py-3">
            <span className="score-value text-xs font-medium text-accent">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="text-xs font-semibold text-primary">{stage.name}</span>
            <span className="mt-0.5 text-xs leading-4 text-secondary">
              {stage.detail}
            </span>
          </div>
          {index < PIPELINE_STAGES.length - 1 ? (
            <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-secondary" />
          ) : null}
        </li>
      ))}
    </ol>
  );
}
