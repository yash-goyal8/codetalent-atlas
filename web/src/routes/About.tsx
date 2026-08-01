import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Card, CardContent, CardTitle } from "../components/ui/card";

export default function About() {
  return (
    <PageContainer>
      <PageHeader
        title="About CodeTalent Atlas"
        description="A zero-cost, research-grade market-intelligence project that maps where strong Cloud and DevOps open-source contributors are located, built entirely on public data."
      />

      <section aria-label="Project principles" className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardTitle>Public data only</CardTitle>
          <CardContent className="mt-2 text-xs leading-5 text-secondary">
            Every signal comes from public GitHub activity via the GH Archive
            BigQuery dataset and the public GitHub API. No scraping, no private
            data, no paid services.
          </CardContent>
        </Card>
        <Card>
          <CardTitle>Aggregate-only output</CardTitle>
          <CardContent className="mt-2 text-xs leading-5 text-secondary">
            Published outputs are geographic aggregates. Individual developer
            usernames, profiles, and raw locations never appear in this
            interface or its data files.
          </CardContent>
        </Card>
        <Card>
          <CardTitle>Reproducible methodology</CardTitle>
          <CardContent className="mt-2 text-xs leading-5 text-secondary">
            Every score is produced by a documented, versioned pipeline with
            validation and bias reporting. See the Methodology page for the
            complete recipe.
          </CardContent>
        </Card>
      </section>
    </PageContainer>
  );
}
