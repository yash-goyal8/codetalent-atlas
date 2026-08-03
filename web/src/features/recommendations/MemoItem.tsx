import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { ConfidenceBadge } from "../../components/ConfidenceBadge";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { formatCount, formatScore } from "../../lib/format";
import type { RecommendationItem } from "../../types/data";
import { subdomainIdLabel } from "../shared/geo";

/**
 * One executive-memo recommendation (spec 19.7, spec 23 template):
 * "Investigate [Location] for [Subdomain] contributors" with evidence,
 * confidence, risk, and the suggested pilot action — all verbatim or
 * formatted from recommendations.json, never pre-written.
 */
export function MemoItem({ item }: { item: RecommendationItem }) {
  const subdomainList = item.subdomains.map(subdomainIdLabel).join(", ");
  return (
    <Card className="space-y-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold text-primary">
          <span className="score-value text-secondary">#{item.rank}</span>{" "}
          Investigate {item.name} for {subdomainList} contributors
        </h3>
        <ConfidenceBadge score={item.confidenceScore} />
      </div>

      <dl className="flex flex-wrap gap-x-8 gap-y-2 text-xs">
        <div>
          <dt className="text-secondary">Opportunity</dt>
          <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
            {formatScore(item.opportunityScore)}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Confidence</dt>
          <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
            {formatScore(item.confidenceScore)}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Observable pool</dt>
          <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
            {formatCount(item.observablePool)}
          </dd>
        </div>
        <div>
          <dt className="text-secondary">Relevant subdomains</dt>
          <dd className="mt-1 flex flex-wrap gap-1.5">
            {item.subdomains.map((subdomain) => (
              <Badge key={subdomain} variant="accent">
                {subdomainIdLabel(subdomain)}
              </Badge>
            ))}
          </dd>
        </div>
      </dl>

      <dl className="space-y-3 border-t border-border pt-4 text-sm leading-6">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-secondary">
            Why now
          </dt>
          <dd className="mt-1 text-primary">{item.whyNow}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-secondary">
            Main risk
          </dt>
          <dd className="mt-1 text-primary">{item.risk}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-secondary">
            Suggested next step
          </dt>
          <dd className="mt-1 text-primary">{item.suggestedPilot}</dd>
        </div>
      </dl>

      <Link
        to={`/location/${encodeURIComponent(item.geoId)}`}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-accent hover:underline"
      >
        Full profile for {item.name}
        <ArrowRight aria-hidden="true" className="size-3.5" />
      </Link>
    </Card>
  );
}
