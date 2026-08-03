import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { TierBadge } from "../../components/TierBadge";
import { formatScore } from "../../lib/format";
import type { TopPriorityLocation } from "../../types/data";
import { countryFlag } from "../shared/geo";

interface TopLocationsProps {
  locations: TopPriorityLocation[];
}

/**
 * Top-five priority locations list (spec 19.1): rank, flag, name,
 * opportunity and confidence scores, tier badge, and a detail link.
 */
export function TopLocations({ locations }: TopLocationsProps) {
  const top = locations.slice(0, 5);
  return (
    <ol className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
      {top.map((location, index) => (
        <li key={location.geoId}>
          <Link
            to={`/location/${encodeURIComponent(location.geoId)}`}
            className="group flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 transition-colors duration-150 hover:bg-surface-2/60"
          >
            <span className="score-value w-6 shrink-0 text-sm font-semibold text-secondary">
              {index + 1}
            </span>
            <span aria-hidden="true" className="text-lg leading-none">
              {countryFlag(location.countryCode)}
            </span>
            <span className="min-w-32 flex-1 text-sm font-medium text-primary">
              {location.name}
            </span>
            <span className="text-xs text-secondary">
              Opportunity{" "}
              <span className="score-value font-semibold text-primary">
                {formatScore(location.opportunityScore)}
              </span>
            </span>
            <span className="text-xs text-secondary">
              Confidence{" "}
              <span className="score-value font-semibold text-primary">
                {formatScore(location.confidenceScore)}
              </span>
            </span>
            <TierBadge tier={location.tier} />
            <ArrowRight
              aria-hidden="true"
              className="size-4 text-secondary opacity-0 transition-opacity duration-150 group-hover:opacity-100"
            />
          </Link>
        </li>
      ))}
    </ol>
  );
}
