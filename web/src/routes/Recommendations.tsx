import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Skeleton } from "../components/Skeleton";
import { Badge } from "../components/ui/badge";
import { loadRecommendations } from "../lib/data";
import type { RecommendationsFile } from "../types/data";
import { MemoItem } from "../features/recommendations/MemoItem";
import { DataGate } from "../features/shared/DataGate";
import { formatDateTime } from "../features/shared/format";
import { useDataFile } from "../features/shared/useDataFile";

export default function Recommendations() {
  const state = useDataFile<RecommendationsFile>(loadRecommendations);

  return (
    <PageContainer className="max-w-4xl">
      <PageHeader
        title="Recommendations"
        description="An executive memo with the recommended sourcing pilots: why now, relevant subdomains, observable pool size, confidence, the main risk, and a suggested pilot action. Every recommendation is assembled from published evidence — never pre-written."
      />
      <DataGate
        state={state}
        skeleton={
          <div className="space-y-4">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        }
        emptyDetail="Recommendations are generated after the validated pilot dataset exists — none are pre-written."
      >
        {(recommendations) =>
          recommendations.items.length > 0 ? (
            <div className="space-y-6">
              <Badge variant="neutral">
                Memo generated{" "}
                <span className="score-value">
                  {formatDateTime(recommendations.generatedAt)}
                </span>
              </Badge>
              <ol className="list-none space-y-6">
                {recommendations.items.map((item) => (
                  <li key={item.geoId}>
                    <MemoItem item={item} />
                  </li>
                ))}
              </ol>
              <p className="text-xs leading-5 text-secondary">
                Each pilot suggestion is a small sourcing experiment: validate
                response and qualification rates before scaling. Confidence
                caveats and full limitations are documented on the Methodology
                page.
              </p>
            </div>
          ) : (
            <EmptyState detail="The published recommendations file contains no items for this dataset window." />
          )
        }
      </DataGate>
    </PageContainer>
  );
}
