import { EmptyState } from "../components/EmptyState";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";

export default function Explorer() {
  return (
    <PageContainer>
      <PageHeader
        title="Geographic explorer"
        description="An interactive country choropleth and city map colored by opportunity score, with confidence shown through opacity and borders, alongside a ranked location rail with subdomain, time-window, and confidence filters. The map ships in a later milestone using local GeoJSON — no external tile services."
      />
      <EmptyState detail="Country and city rankings, score-layer toggles, and the location rail will render here from the published rankings files." />
    </PageContainer>
  );
}
