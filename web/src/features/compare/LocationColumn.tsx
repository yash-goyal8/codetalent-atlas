import { X } from "lucide-react";
import { Link } from "react-router-dom";
import { ScoreBar } from "../../components/ScoreBar";
import { TierBadge } from "../../components/TierBadge";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { formatCount, formatScore, formatShare } from "../../lib/format";
import type { GeographicRankingRow } from "../../types/data";
import { COMPONENT_LABELS } from "../detail/statements";
import { countryFlag, subdomainIdLabel } from "../shared/geo";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-xs text-secondary">{label}</dt>
      <dd className="score-value text-sm font-medium text-primary">{value}</dd>
    </div>
  );
}

interface LocationColumnProps {
  row: GeographicRankingRow;
  onRemove: (geoId: string) => void;
}

/**
 * One side-by-side comparison column (spec 19.5). Every column renders
 * the identical section order so score bars align across columns.
 */
export function LocationColumn({ row, onRemove }: LocationColumnProps) {
  return (
    <Card className="flex h-full flex-col gap-4">
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-primary">
            <span aria-hidden="true" className="text-lg leading-none">
              {countryFlag(row.countryCode)}
            </span>
            <Link
              to={`/location/${encodeURIComponent(row.geoId)}`}
              className="hover:underline"
            >
              {row.name}
            </Link>
          </h3>
          <p className="text-xs text-secondary">
            {row.geoLevel === "country" ? "Country" : "City"} · Rank{" "}
            <span className="score-value">#{row.rank}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => onRemove(row.geoId)}
          aria-label={`Remove ${row.name} from comparison`}
          className="rounded-md p-1 text-secondary transition-colors duration-150 hover:bg-surface-2 hover:text-primary"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      </div>

      <TierBadge tier={row.recommendationTier} className="self-start" />

      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-md border border-border bg-surface-2/60 px-3 py-2">
          <dt className="text-[11px] text-secondary">Opportunity</dt>
          <dd className="score-value text-2xl font-semibold text-primary">
            {formatScore(row.opportunityScore)}
          </dd>
        </div>
        <div className="rounded-md border border-border bg-surface-2/60 px-3 py-2">
          <dt className="text-[11px] text-secondary">Confidence</dt>
          <dd className="score-value text-2xl font-semibold text-primary">
            {formatScore(row.confidenceScore)}
          </dd>
        </div>
      </dl>

      <div className="space-y-2">
        <h4 className="text-xs font-medium text-secondary">Score components</h4>
        <ScoreBar label={COMPONENT_LABELS.expertSupplyScore} value={row.expertSupplyScore} />
        <ScoreBar label={COMPONENT_LABELS.expertQualityScore} value={row.expertQualityScore} />
        <ScoreBar
          label={COMPONENT_LABELS.collaborationDepthScore}
          value={row.collaborationDepthScore}
        />
        <ScoreBar
          label={
            row.momentumProvisional
              ? `${COMPONENT_LABELS.momentumScore} (provisional)`
              : COMPONENT_LABELS.momentumScore
          }
          value={row.momentumScore}
        />
        <ScoreBar
          label={COMPONENT_LABELS.ecosystemBreadthScore}
          value={row.ecosystemBreadthScore}
        />
      </div>

      <dl className="space-y-1.5 border-t border-border pt-3">
        <Row label="Observable experts" value={formatCount(row.observableExpertCount)} />
        <Row label="Weighted experts" value={formatCount(row.weightedExpertCount)} />
        <Row label="Qualified repositories" value={formatCount(row.qualifiedRepoCount)} />
        <Row label="Organizations" value={formatCount(row.organizationCount)} />
        <Row label="Multi-repo expert share" value={formatShare(row.multiRepoExpertShare)} />
        <Row
          label="Located-profile coverage"
          value={formatShare(row.locatedProfileCoverage)}
        />
        <Row
          label="High-confidence locations"
          value={formatShare(row.highConfidenceLocationShare)}
        />
      </dl>

      {row.topSubdomains.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
          <span className="text-xs text-secondary">Subdomain strengths:</span>
          {row.topSubdomains.map((subdomain) => (
            <Badge key={subdomain} variant="neutral">
              {subdomainIdLabel(subdomain)}
            </Badge>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
