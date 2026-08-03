import { Check, CircleAlert, X } from "lucide-react";
import { Card, CardTitle } from "../../components/ui/card";
import { formatShare } from "../../lib/format";
import type { ValidationFile } from "../../types/data";
import { formatBytes } from "../shared/format";

const PRECISION_METRICS: {
  label: string;
  value: (v: ValidationFile) => number;
}[] = [
  { label: "Repository classification precision", value: (v) => v.classificationPrecision },
  { label: "Location precision (country)", value: (v) => v.locationCountryPrecision },
  { label: "Location precision (city)", value: (v) => v.locationCityPrecision },
];

function CheckStatus({ status }: { status: string }) {
  if (status === "pass") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-positive">
        <Check aria-hidden="true" className="size-3.5" />
        Pass
      </span>
    );
  }
  if (status === "warn") {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-warning">
        <CircleAlert aria-hidden="true" className="size-3.5" />
        Warn
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-risk">
      <X aria-hidden="true" className="size-3.5" />
      {status}
    </span>
  );
}

/**
 * Validation results block (spec 19.6): manual-sample precision
 * numbers, quality-check list with pass marks, and processing budget.
 */
export function ValidationResults({ validation }: { validation: ValidationFile }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardTitle>Manual validation precision</CardTitle>
        <dl className="mt-3 space-y-2">
          {PRECISION_METRICS.map((metric) => (
            <div
              key={metric.label}
              className="flex items-baseline justify-between gap-3"
            >
              <dt className="text-xs text-secondary">{metric.label}</dt>
              <dd className="score-value text-sm font-semibold text-primary">
                {formatShare(metric.value(validation))}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-4 border-t border-border pt-3 text-xs text-secondary">
          BigQuery processing:{" "}
          <span className="score-value font-medium text-primary">
            {formatBytes(validation.budget.bytesProcessed)}
          </span>{" "}
          ({formatShare(validation.budget.freeTierShare)} of the free tier).
        </p>
      </Card>
      <Card>
        <CardTitle>Data quality checks</CardTitle>
        <ul className="mt-3 space-y-2">
          {validation.qualityChecks.map((check) => (
            <li
              key={check.name}
              className="flex items-center justify-between gap-3 text-xs text-primary"
            >
              <span>{check.name}</span>
              <CheckStatus status={check.status} />
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
