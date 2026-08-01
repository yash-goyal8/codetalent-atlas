import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";

export default function Recommendations() {
  return (
    <PageContainer>
      <PageHeader
        title="Recommendations"
        description="An executive memo with the top three recommended sourcing pilots: why now, relevant subdomains, observable pool size, confidence, the main risk, and a suggested pilot action. Every recommendation is assembled from published evidence — never pre-written."
      />
      <EmptyState detail="Recommendations are generated strictly from pipeline output, so none exist before the first run." />
    </PageContainer>
  );
}
