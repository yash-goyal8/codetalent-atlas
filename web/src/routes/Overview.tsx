import { useCallback } from "react";
import { PageContainer } from "../components/PageContainer";
import { Skeleton } from "../components/Skeleton";
import { Badge } from "../components/ui/badge";
import { useManifest } from "../hooks/useManifest";
import { loadRankings, loadRecommendations, loadSummary } from "../lib/data";
import type { RankingsFile, RecommendationsFile, Summary } from "../types/data";
import { KpiCards } from "../features/overview/KpiCards";
import { LimitationsNote } from "../features/overview/LimitationsNote";
import { MethodologySummary } from "../features/overview/MethodologySummary";
import { OpportunityConfidenceScatter } from "../features/overview/OpportunityConfidenceScatter";
import { RecommendationTeasers } from "../features/overview/RecommendationTeasers";
import { SubdomainHubs } from "../features/overview/SubdomainHubs";
import { TopLocations } from "../features/overview/TopLocations";
import { DataGate } from "../features/shared/DataGate";
import { Section } from "../features/shared/Section";
import { useDataFile } from "../features/shared/useDataFile";

/** Data-window label from the manifest (spec 19.1, above the fold). */
function DataWindowLabel() {
  const manifest = useManifest();
  if (manifest.kind === "loading") {
    return <Skeleton className="h-6 w-56" />;
  }
  if (manifest.kind === "missing") {
    return <Badge variant="neutral">Data window: awaiting first dataset</Badge>;
  }
  const { start, end } = manifest.manifest.window;
  return (
    <Badge variant="neutral">
      Data window: <span className="score-value">{start}</span> to{" "}
      <span className="score-value">{end}</span>
    </Badge>
  );
}

export default function Overview() {
  const summaryState = useDataFile<Summary>(loadSummary);
  const rankingsState = useDataFile<RankingsFile>(
    useCallback(() => loadRankings("country"), []),
  );
  const recommendationsState =
    useDataFile<RecommendationsFile>(loadRecommendations);

  return (
    <PageContainer>
      <header className="max-w-3xl space-y-3">
        <h1 className="text-2xl font-semibold tracking-tight text-primary">
          Executive overview
        </h1>
        <p className="text-sm leading-6 text-secondary">
          Where the strongest observable Cloud and DevOps open-source
          contributors are located — evidence-based sourcing intelligence built
          entirely from public GitHub activity.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {/* Single pilot domain; a real selector activates with expansion domains. */}
          <Badge variant="accent">Domain: Cloud and DevOps</Badge>
          <DataWindowLabel />
        </div>
      </header>

      <Section title="Headline metrics">
        <KpiCards state={summaryState} />
      </Section>

      <Section
        title="Top priority locations"
        description="The five strongest ranked locations by opportunity score, with confidence shown alongside — click through for the full profile."
      >
        <DataGate
          state={summaryState}
          skeleton={
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          }
          emptyDetail="Priority locations appear once the pilot pipeline publishes its first summary dataset."
        >
          {(summary) =>
            summary.topPriorityLocations.length > 0 ? (
              <TopLocations locations={summary.topPriorityLocations} />
            ) : (
              <p className="rounded-lg border border-border bg-surface-1 px-4 py-6 text-center text-xs text-secondary">
                No location met the priority thresholds in this dataset window.
              </p>
            )
          }
        </DataGate>
      </Section>

      <Section
        title="Opportunity vs confidence"
        description="Every ranked country plotted by how strong its observable expert pool looks (opportunity) against how much the data can be trusted (confidence). The two are never merged."
      >
        <DataGate
          state={rankingsState}
          skeleton={<Skeleton className="h-80 w-full" />}
          emptyDetail="The scatterplot renders from the published country rankings file."
        >
          {(rankings) => <OpportunityConfidenceScatter rows={rankings.rows} />}
        </DataGate>
      </Section>

      <Section
        title="Top subdomain hubs"
        description="The leading country per Cloud/DevOps subdomain by observable expert count."
      >
        <DataGate
          state={summaryState}
          skeleton={
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
              <Skeleton className="h-28" />
            </div>
          }
          emptyDetail="Subdomain hubs are published with the summary dataset."
        >
          {(summary) =>
            summary.subdomainHubs.length > 0 ? (
              <SubdomainHubs hubs={summary.subdomainHubs} />
            ) : (
              <p className="rounded-lg border border-border bg-surface-1 px-4 py-6 text-center text-xs text-secondary">
                No subdomain reached the minimum sample size in this window.
              </p>
            )
          }
        </DataGate>
      </Section>

      <Section title="Methodology at a glance">
        <MethodologySummary />
      </Section>

      <Section
        title="Recommended sourcing pilots"
        description="Teasers from the executive recommendations memo — generated strictly from published evidence."
      >
        <DataGate
          state={recommendationsState}
          skeleton={
            <div className="grid gap-4 lg:grid-cols-3">
              <Skeleton className="h-36" />
              <Skeleton className="h-36" />
              <Skeleton className="h-36" />
            </div>
          }
          emptyDetail="Recommendations are generated after the validated pilot dataset exists — none are pre-written."
        >
          {(recommendations) => (
            <RecommendationTeasers items={recommendations.items} />
          )}
        </DataGate>
      </Section>

      <LimitationsNote />
    </PageContainer>
  );
}
