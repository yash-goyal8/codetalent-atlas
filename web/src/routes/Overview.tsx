import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Badge } from "../components/ui/badge";
import { Card, CardDescription, CardTitle } from "../components/ui/card";

/** KPI card definitions from spec section 19.1; values arrive with the first dataset. */
const kpis = [
  "Qualified repositories",
  "Observable experts",
  "Located-profile coverage",
  "Countries with sufficient data",
] as const;

export default function Overview() {
  return (
    <PageContainer>
      <PageHeader
        title="Executive overview"
        description="Where the strongest observable Cloud and DevOps open-source contributors are located. This page will present the data window, four headline KPIs, a globe preview, the top five priority locations, an opportunity-versus-confidence scatterplot, and evidence-backed recommendations."
      >
        <Badge variant="accent">Pilot domain: Cloud and DevOps</Badge>
      </PageHeader>

      <section aria-label="Headline metrics">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((label) => (
            <Card key={label}>
              <CardTitle className="text-xs font-medium text-secondary">
                {label}
              </CardTitle>
              <p
                aria-label={`${label}: not yet available`}
                className="score-value mt-2 text-3xl font-semibold text-primary"
              >
                &mdash;
              </p>
              <CardDescription className="mt-1">
                Populated after the first pipeline run
              </CardDescription>
            </Card>
          ))}
        </div>
      </section>

      <EmptyState detail="Once published, this overview will surface top priority locations, the opportunity-versus-confidence landscape, a methodology summary, and known limitations." />
    </PageContainer>
  );
}
