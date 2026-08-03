import { Card, CardDescription, CardTitle } from "../../components/ui/card";
import { Skeleton } from "../../components/Skeleton";
import { formatCount, formatShare, NO_VALUE } from "../../lib/format";
import type { Summary } from "../../types/data";
import type { DataState } from "../shared/useDataFile";

interface KpiDefinition {
  label: string;
  /** Formatted value straight from summary KPIs — never invented. */
  value: (summary: Summary) => string;
}

/** The four headline KPI cards from spec section 19.1. */
const KPI_DEFINITIONS: KpiDefinition[] = [
  {
    label: "Qualified repositories",
    value: (s) => formatCount(s.kpis.qualifiedRepositories),
  },
  {
    label: "Observable experts",
    value: (s) => formatCount(s.kpis.observableExperts),
  },
  {
    label: "Located-profile coverage",
    value: (s) => formatShare(s.kpis.locatedProfileCoverage),
  },
  {
    label: "Countries with sufficient data",
    value: (s) => formatCount(s.kpis.countriesWithSufficientData),
  },
];

interface KpiCardsProps {
  state: DataState<Summary>;
}

/**
 * Four KPI cards with skeletons while loading and designed placeholder
 * values when the dataset is missing or failed to load.
 */
export function KpiCards({ state }: KpiCardsProps) {
  const summary = state.status === "ok" ? state.data : null;
  const note =
    state.status === "missing"
      ? "Populated after the first pipeline run"
      : state.status === "error"
        ? "Data file failed to load"
        : null;

  return (
    <div
      role={state.status === "loading" ? "status" : undefined}
      aria-label={state.status === "loading" ? "Loading headline metrics" : undefined}
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
    >
      {KPI_DEFINITIONS.map((kpi) => {
        const value = summary ? kpi.value(summary) : NO_VALUE;
        return (
          <Card key={kpi.label}>
            <CardTitle className="text-xs font-medium text-secondary">
              {kpi.label}
            </CardTitle>
            {state.status === "loading" ? (
              <Skeleton className="mt-3 h-8 w-24" />
            ) : (
              <p
                aria-label={`${kpi.label}: ${summary ? value : "not yet available"}`}
                className="score-value mt-2 text-3xl font-semibold text-primary"
              >
                {value}
              </p>
            )}
            {note ? (
              <CardDescription className="mt-1">{note}</CardDescription>
            ) : null}
          </Card>
        );
      })}
    </div>
  );
}
