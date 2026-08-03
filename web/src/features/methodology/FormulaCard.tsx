import { Card, CardDescription, CardTitle } from "../../components/ui/card";
import type { ScoreFormula } from "./content";

/**
 * One score-formula card (spec 19.6): component labels with weight bars
 * showing the exact configured percentages. The number is always
 * printed, so bar length never carries meaning alone.
 */
export function FormulaCard({ formula }: { formula: ScoreFormula }) {
  return (
    <Card className="h-full">
      <CardTitle>{formula.title}</CardTitle>
      <CardDescription className="mt-1">{formula.description}</CardDescription>
      <dl className="mt-4 space-y-2.5">
        {formula.components.map((component) => (
          <div key={component.label} className="flex items-center gap-3">
            <dt className="w-48 shrink-0 truncate text-xs text-secondary">
              {component.label}
            </dt>
            <dd className="flex min-w-0 flex-1 items-center gap-3">
              <div
                aria-hidden="true"
                className="h-1.5 min-w-8 flex-1 overflow-hidden rounded-full bg-surface-2"
              >
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${component.weight}%` }}
                />
              </div>
              <span className="score-value w-9 shrink-0 text-right text-xs font-medium text-primary">
                {component.weight}%
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
