import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Card, CardDescription, CardTitle } from "../components/ui/card";

const sections = [
  {
    title: "Pipeline and data funnel",
    description:
      "How public GitHub activity flows from BigQuery discovery through enrichment, location normalization, and scoring to aggregate outputs.",
  },
  {
    title: "Scoring formulas",
    description:
      "Repository quality, contributor expertise, and the geographic opportunity and confidence scores, with inclusion and exclusion rules.",
  },
  {
    title: "Validation and limitations",
    description:
      "Classification and location validation results, ranking sensitivity analysis, coverage bias, and known representation limits.",
  },
] as const;

export default function Methodology() {
  return (
    <PageContainer>
      <PageHeader
        title="Methodology"
        description="The full recipe behind every score: pipeline diagram, data funnel, inclusion and exclusion rules, score formulas, validation results, sensitivity analysis, limitations, data freshness, and an aggregate-data download."
      />

      <section aria-label="Methodology sections" className="grid gap-4 lg:grid-cols-3">
        {sections.map((section) => (
          <Card key={section.title}>
            <CardTitle>{section.title}</CardTitle>
            <CardDescription className="mt-2">
              {section.description}
            </CardDescription>
          </Card>
        ))}
      </section>

      <EmptyState detail="Validation results, coverage charts, and the aggregate-data download appear here after the pilot pipeline publishes its methodology files." />
    </PageContainer>
  );
}
