import { useCallback } from "react";
import { GitCompareArrows, MapPinOff } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { PageContainer } from "../components/PageContainer";
import { ScoreBar } from "../components/ScoreBar";
import { Skeleton } from "../components/Skeleton";
import { TierBadge } from "../components/TierBadge";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { loadLocationDetail } from "../lib/data";
import { formatCount, formatScore, formatShare } from "../lib/format";
import {
  normalizeSelected,
  serializeUrlState,
  useUrlState,
} from "../lib/urlstate";
import type { DataResult } from "../lib/data";
import type { LocationDetail as LocationDetailData } from "../types/data";
import { ActivityTrendChart } from "../features/detail/ActivityTrendChart";
import { SubdomainMixChart } from "../features/detail/SubdomainMixChart";
import {
  COMPONENT_LABELS,
  tierStatement,
  whyStatements,
} from "../features/detail/statements";
import { LoadErrorState } from "../features/shared/LoadErrorState";
import { Section } from "../features/shared/Section";
import { countryFlag, subdomainIdLabel } from "../features/shared/geo";
import { useDataFile } from "../features/shared/useDataFile";

/** Small labeled stat for the metric grids. */
function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
      <dt className="text-xs text-secondary">{label}</dt>
      <dd className="score-value mt-1 text-xl font-semibold text-primary">
        {value}
      </dd>
    </div>
  );
}

/** Adds this location to the URL selection and navigates to Compare. */
function CompareButton({ geoId, name }: { geoId: string; name: string }) {
  const [state] = useUrlState();
  const navigate = useNavigate();
  const onClick = () => {
    const selected = normalizeSelected([...state.selected, geoId]);
    const params = serializeUrlState({ ...state, selected });
    void navigate({ pathname: "/compare", search: params.toString() });
  };
  return (
    <Button variant="primary" size="sm" onClick={onClick}>
      <GitCompareArrows aria-hidden="true" className="size-4" />
      Compare {name}
    </Button>
  );
}

/**
 * Designed not-found / insufficient-data state (spec 19, empty/error
 * states): the geoId is unknown, below sample thresholds, or the
 * dataset has not been published yet.
 */
function LocationUnavailable({ geoId }: { geoId: string | undefined }) {
  return (
    <div
      role="status"
      className="flex flex-col items-center gap-4 rounded-lg border border-dashed border-white/15 bg-surface-1 px-6 py-14 text-center"
    >
      <span
        aria-hidden="true"
        className="flex size-12 items-center justify-center rounded-full border border-border bg-surface-2"
      >
        <MapPinOff className="size-6 text-secondary" />
      </span>
      <p className="max-w-md text-sm font-medium text-primary">
        {geoId
          ? `No published data for location "${geoId}"`
          : "No location was requested"}
      </p>
      <p className="max-w-md text-xs leading-5 text-secondary">
        This location is not part of the current dataset — it may be below the
        minimum sample thresholds (insufficient data), the id may be wrong, or
        the pilot pipeline has not published its first dataset yet.
      </p>
      <Link
        to="/explore"
        className="text-xs font-medium text-accent hover:underline"
      >
        Browse ranked locations in the Explorer
      </Link>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div role="status" aria-label="Loading location detail" className="space-y-6">
      <Skeleton className="h-24 w-full max-w-2xl" />
      <Skeleton className="h-40 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

/** Full profile once the location file resolved (spec 19.4). */
function DetailContent({ detail }: { detail: LocationDetailData }) {
  const { ranking, components, subdomainMix, activityTrend, concentration, coverage, caveats } =
    detail;
  const singleRepoShare = concentration.singleRepoShare;

  return (
    <>
      {/* Hero (spec 19.4): name + flag, both scores side by side, tier, statement. */}
      <header className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <span aria-hidden="true" className="text-3xl leading-none">
            {countryFlag(ranking.countryCode)}
          </span>
          <h1 className="text-2xl font-semibold tracking-tight text-primary">
            {ranking.name}
          </h1>
          <Badge variant="neutral">
            {ranking.geoLevel === "country" ? "Country" : "City"} · Rank{" "}
            <span className="score-value">#{ranking.rank}</span>
          </Badge>
          <TierBadge tier={ranking.recommendationTier} />
        </div>
        <dl className="flex flex-wrap gap-4">
          <div className="min-w-44 rounded-lg border border-border bg-surface-1 px-5 py-4">
            <dt className="text-xs text-secondary">Opportunity score</dt>
            <dd className="score-value mt-1 text-4xl font-semibold text-primary">
              {formatScore(ranking.opportunityScore)}
            </dd>
          </div>
          <div className="min-w-44 rounded-lg border border-border bg-surface-1 px-5 py-4">
            <dt className="text-xs text-secondary">Confidence score</dt>
            <dd className="score-value mt-1 text-4xl font-semibold text-primary">
              {formatScore(ranking.confidenceScore)}
            </dd>
            <ConfidenceBadge
              score={ranking.confidenceScore}
              showScore={false}
              className="mt-2"
            />
          </div>
        </dl>
        <p className="max-w-2xl text-sm leading-6 text-secondary">
          {tierStatement(ranking.recommendationTier)}
        </p>
        <CompareButton geoId={ranking.geoId} name={ranking.name} />
      </header>

      <Section
        title="Score decomposition"
        description="The five components behind the opportunity score, each on the shared 0-100 scale."
      >
        <Card className="space-y-3">
          <ScoreBar
            label={COMPONENT_LABELS.expertSupplyScore}
            value={components.expertSupplyScore}
          />
          <ScoreBar
            label={COMPONENT_LABELS.expertQualityScore}
            value={components.expertQualityScore}
          />
          <ScoreBar
            label={COMPONENT_LABELS.collaborationDepthScore}
            value={components.collaborationDepthScore}
          />
          <ScoreBar
            label={
              ranking.momentumProvisional
                ? `${COMPONENT_LABELS.momentumScore} (provisional)`
                : COMPONENT_LABELS.momentumScore
            }
            value={components.momentumScore}
          />
          <ScoreBar
            label={COMPONENT_LABELS.ecosystemBreadthScore}
            value={components.ecosystemBreadthScore}
          />
        </Card>
      </Section>

      <Section
        title="Expert supply and quality"
        description="Raw and weighted pool sizes are always shown together (spec safeguard) — weighted counts discount low-evidence contributors."
      >
        <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Observable experts (raw)"
            value={formatCount(ranking.observableExpertCount)}
          />
          <Stat
            label="Weighted experts"
            value={formatCount(ranking.weightedExpertCount)}
          />
          <Stat
            label="Expert supply score"
            value={formatScore(ranking.expertSupplyScore)}
          />
          <Stat
            label="Expert quality score"
            value={formatScore(ranking.expertQualityScore)}
          />
        </dl>
      </Section>

      <Section
        title="Activity trend"
        description="Monthly weighted events and active contributors inside the dataset window."
      >
        {activityTrend.length > 0 ? (
          <ActivityTrendChart trend={activityTrend} locationName={ranking.name} />
        ) : (
          <p
            role="status"
            className="rounded-lg border border-border bg-surface-1 px-4 py-6 text-center text-xs text-secondary"
          >
            No trend data for the pilot window — monthly activity appears with
            the expanded twelve-month dataset.
          </p>
        )}
      </Section>

      <Section
        title="Subdomain mix"
        description="Where this location's observable experts are active across Cloud/DevOps subdomains."
      >
        {subdomainMix.length > 0 ? (
          <SubdomainMixChart mix={subdomainMix} locationName={ranking.name} />
        ) : (
          <p
            role="status"
            className="rounded-lg border border-border bg-surface-1 px-4 py-6 text-center text-xs text-secondary"
          >
            No subdomain reached the minimum sample size for this location.
          </p>
        )}
      </Section>

      <Section
        title="Repository and organization breadth"
        description="How broad the qualified open-source ecosystem behind this location is."
      >
        <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Qualified repositories"
            value={formatCount(ranking.qualifiedRepoCount)}
          />
          <Stat
            label="Distinct organizations"
            value={formatCount(ranking.organizationCount)}
          />
          <Stat
            label="Multi-repo expert share"
            value={formatShare(ranking.multiRepoExpertShare)}
          />
          <Stat
            label="Ecosystem breadth score"
            value={formatScore(ranking.ecosystemBreadthScore)}
          />
        </dl>
        {ranking.topSubdomains.length > 0 ? (
          <p className="flex flex-wrap items-center gap-2 text-xs text-secondary">
            Top subdomains:
            {ranking.topSubdomains.map((subdomain) => (
              <Badge key={subdomain} variant="neutral">
                {subdomainIdLabel(subdomain)}
              </Badge>
            ))}
          </p>
        ) : null}
      </Section>

      <Section
        title="Concentration risk"
        description="Rankings are less reliable when activity concentrates in one organization or one repository."
      >
        <Card className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {concentration.flagged ? (
              <Badge variant="risk">Concentration flagged</Badge>
            ) : (
              <Badge variant="positive">No concentration flag</Badge>
            )}
            <span className="text-xs text-secondary">
              {concentration.flagged
                ? "A single organization contributes more than 20% of this location's weighted activity, so scores may over-represent one employer."
                : "No single organization exceeds the 20% weighted-activity threshold."}
            </span>
          </div>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Stat
              label="Top organization share of weighted activity"
              value={formatShare(concentration.topOrgShare)}
            />
            <Stat
              label="Experts observed in only one repository"
              value={formatShare(singleRepoShare)}
            />
          </dl>
        </Card>
      </Section>

      <Section
        title="Why this location ranks here"
        description="Assembled from this location's published component values — no editorial judgment."
      >
        <Card>
          <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6 text-primary">
            {whyStatements(detail).map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        </Card>
      </Section>

      <Section
        title="Data coverage and caveats"
        description="How complete the location evidence is for this geography, plus pipeline-published caveats."
      >
        <dl className="grid gap-4 sm:grid-cols-3">
          <Stat
            label="Located-profile coverage"
            value={formatShare(coverage.locatedProfileCoverage)}
          />
          <Stat
            label="High-confidence location share"
            value={formatShare(coverage.highConfidenceLocationShare)}
          />
          <Stat
            label="Observable experts"
            value={formatCount(coverage.observableExpertCount)}
          />
        </dl>
        {caveats.length > 0 ? (
          <Card>
            <CardTitle className="text-xs font-medium text-secondary">
              Caveats
            </CardTitle>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-5 text-secondary">
              {caveats.map((caveat) => (
                <li key={caveat}>{caveat}</li>
              ))}
            </ul>
          </Card>
        ) : null}
      </Section>
    </>
  );
}

export default function LocationDetail() {
  const { geoId } = useParams<"geoId">();

  const load = useCallback((): Promise<DataResult<LocationDetailData>> => {
    if (!geoId) {
      return Promise.resolve({ status: "missing" });
    }
    return loadLocationDetail(geoId);
  }, [geoId]);
  const state = useDataFile<LocationDetailData>(load);

  // Non-ok states keep the generic h1 so the page always has a heading.
  if (state.status !== "ok") {
    return (
      <PageContainer>
        <header className="max-w-3xl space-y-3">
          <h1 className="text-2xl font-semibold tracking-tight text-primary">
            Location detail
          </h1>
          <p className="text-sm leading-6 text-secondary">
            A full profile for one country or city: scores, decomposition,
            trends, breadth, risks, and caveats. No developer usernames are
            ever shown.
          </p>
        </header>
        {state.status === "loading" ? (
          <DetailSkeleton />
        ) : state.status === "error" ? (
          <LoadErrorState detail={state.message} />
        ) : (
          <LocationUnavailable geoId={geoId} />
        )}
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <DetailContent detail={state.data} />
    </PageContainer>
  );
}
