import { useParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { Badge } from "../components/ui/badge";

export default function LocationDetail() {
  const { geoId } = useParams<"geoId">();

  return (
    <PageContainer>
      <PageHeader
        title="Location detail"
        description="A full profile for one country or city: opportunity and confidence scores, recommendation tier, score decomposition, expert supply and quality distribution, activity trend, subdomain mix, repository breadth, concentration risk, and an explanation of why the location ranks where it does. No developer usernames are ever shown."
      >
        {geoId ? (
          <Badge variant="neutral">
            Requested location id: <span className="score-value">{geoId}</span>
          </Badge>
        ) : null}
      </PageHeader>
      <EmptyState detail="This location cannot be resolved until the first dataset is published; per-location files load lazily from the data manifest." />
    </PageContainer>
  );
}
