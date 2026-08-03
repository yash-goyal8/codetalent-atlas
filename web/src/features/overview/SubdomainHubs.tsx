import { Card, CardTitle } from "../../components/ui/card";
import { formatCount } from "../../lib/format";
import type { SubdomainHub } from "../../types/data";
import { countryFlag } from "../shared/geo";

interface SubdomainHubsProps {
  hubs: SubdomainHub[];
}

/**
 * Top subdomain hubs strip (spec 19.1): the leading country per
 * subdomain with its observable expert count.
 */
export function SubdomainHubs({ hubs }: SubdomainHubsProps) {
  return (
    <ul className="grid list-none gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {hubs.map((hub) => (
        <li key={hub.subdomainId}>
          <Card className="h-full">
            <CardTitle className="text-xs font-medium text-secondary">
              {hub.displayName}
            </CardTitle>
            <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <span aria-hidden="true" className="text-lg leading-none">
                {countryFlag(hub.topCountry)}
              </span>
              <span>
                Top country: <span className="score-value">{hub.topCountry}</span>
              </span>
            </p>
            <p className="mt-1 text-xs text-secondary">
              <span className="score-value font-medium text-primary">
                {formatCount(hub.expertCount)}
              </span>{" "}
              observable experts
            </p>
          </Card>
        </li>
      ))}
    </ul>
  );
}
