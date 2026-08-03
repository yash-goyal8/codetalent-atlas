import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { Card, CardTitle } from "../../components/ui/card";

/**
 * Compact methodology summary block for the overview (spec 19.1), with
 * a link to the full methodology page. Static definition text only.
 */
export function MethodologySummary() {
  return (
    <Card>
      <CardTitle>How these rankings are built</CardTitle>
      <p className="mt-2 max-w-3xl text-xs leading-5 text-secondary">
        Every score is derived from public GitHub activity: GH Archive events
        surface candidate repositories, deterministic rules qualify genuinely
        active collaborative projects, and contributor evidence is aggregated
        into location-level scores. Opportunity (how strong the observable
        expert pool looks) and confidence (how much to trust the data for that
        location) are always computed and shown separately — a high opportunity
        score with low confidence is never labeled a priority.
      </p>
      <Link
        to="/methodology"
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline"
      >
        Full methodology: pipeline, formulas, validation, limitations
        <ArrowRight aria-hidden="true" className="size-3.5" />
      </Link>
    </Card>
  );
}
