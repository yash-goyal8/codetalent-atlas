import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";

export default function Compare() {
  return (
    <PageContainer>
      <PageHeader
        title="Compare locations"
        description="Side-by-side comparison of two to four locations: opportunity and confidence, score-component bars, expert supply and quality distribution, subdomain strengths, momentum, ecosystem breadth, and coverage or concentration risks — plus a template-assembled factual summary."
      />
      <EmptyState detail="Location selection and comparison panels activate once ranked locations exist to choose from." />
    </PageContainer>
  );
}
