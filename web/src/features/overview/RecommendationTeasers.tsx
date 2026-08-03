import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { ConfidenceBadge } from "../../components/ConfidenceBadge";
import { Card, CardTitle } from "../../components/ui/card";
import { formatScore } from "../../lib/format";
import type { RecommendationItem } from "../../types/data";

interface RecommendationTeasersProps {
  items: RecommendationItem[];
}

/**
 * Three recommendation teasers (spec 19.1), sourced verbatim from
 * `recommendations/<domain>.json` — never pre-written.
 */
export function RecommendationTeasers({ items }: RecommendationTeasersProps) {
  const top = items.slice(0, 3);
  return (
    <div className="space-y-4">
      <ul className="grid list-none gap-4 lg:grid-cols-3">
        {top.map((item) => (
          <li key={item.geoId}>
            <Card className="flex h-full flex-col gap-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle>
                  <span className="score-value text-secondary">#{item.rank}</span>{" "}
                  {item.name}
                </CardTitle>
                <ConfidenceBadge score={item.confidenceScore} showScore={false} />
              </div>
              <p className="text-xs text-secondary">
                Opportunity{" "}
                <span className="score-value font-semibold text-primary">
                  {formatScore(item.opportunityScore)}
                </span>
                {" · "}Confidence{" "}
                <span className="score-value font-semibold text-primary">
                  {formatScore(item.confidenceScore)}
                </span>
              </p>
              <p className="line-clamp-3 text-xs leading-5 text-secondary">
                {item.whyNow}
              </p>
            </Card>
          </li>
        ))}
      </ul>
      <Link
        to="/recommendations"
        className="inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline"
      >
        Read the full recommendations memo
        <ArrowRight aria-hidden="true" className="size-3.5" />
      </Link>
    </div>
  );
}
