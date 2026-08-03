import { useCallback, useId, useMemo } from "react";
import {
  ArrowUpRight,
  MousePointerClick,
  RotateCcw,
  SearchX,
  TriangleAlert,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { DataTable, type DataTableColumn } from "../components/DataTable";
import { PageContainer } from "../components/PageContainer";
import { PageHeader } from "../components/PageHeader";
import { ScoreBar } from "../components/ScoreBar";
import { Skeleton } from "../components/Skeleton";
import { TierBadge } from "../components/TierBadge";
import { Button } from "../components/ui/button";
import { Card, CardTitle } from "../components/ui/card";
import { cn } from "../lib/cn";
import { DEFAULT_DOMAIN_ID, loadRankings } from "../lib/data";
import { formatCount, formatScore, NO_VALUE } from "../lib/format";
import {
  DEFAULT_URL_STATE,
  useUrlState,
  type ScoreLayer,
  type UrlState,
} from "../lib/urlstate";
import type {
  GeographicRankingRow,
  GeoLevel,
  RecommendationTier,
} from "../types/data";
import { AtlasMap } from "../features/map/AtlasMap";
import { SCORE_LAYER_LABELS, subdomainLabel } from "../features/map/scale";
import { DataGate } from "../features/shared/DataGate";
import { Section } from "../features/shared/Section";
import { countryFlag } from "../features/shared/geo";
import { useDataFile } from "../features/shared/useDataFile";

/** Stable empty-row identity so memoized derivations don't churn. */
const NO_ROWS: GeographicRankingRow[] = [];

const GEO_LEVEL_OPTIONS: Array<{ value: GeoLevel; label: string }> = [
  { value: "country", label: "Countries" },
  { value: "city", label: "Cities" },
];

const SCORE_LAYER_OPTIONS = (
  Object.keys(SCORE_LAYER_LABELS) as ScoreLayer[]
).map((value) => ({ value, label: SCORE_LAYER_LABELS[value] }));

const TIER_OPTIONS: Array<{ value: RecommendationTier; label: string }> = [
  { value: "priority", label: "Priority" },
  { value: "promising", label: "Promising" },
  { value: "monitor", label: "Monitor" },
  { value: "insufficient_data", label: "Insufficient data" },
];

/** Row-filtering rules shared by the map and the ranked rail. */
function applyFilters(
  rows: readonly GeographicRankingRow[],
  state: UrlState,
): GeographicRankingRow[] {
  const query = state.search.trim().toLowerCase();
  return rows.filter((row) => {
    if (state.subdomain !== null && !row.topSubdomains.includes(state.subdomain)) {
      return false;
    }
    if (state.tier !== null && row.recommendationTier !== state.tier) {
      return false;
    }
    if (row.confidenceScore < state.minConfidence) {
      return false;
    }
    if (
      query !== "" &&
      !row.name.toLowerCase().includes(query) &&
      !row.countryCode.toLowerCase().includes(query)
    ) {
      return false;
    }
    return true;
  });
}

/** True when any row-filtering control is off its default. */
function hasActiveFilters(state: UrlState): boolean {
  return (
    state.subdomain !== null ||
    state.tier !== null ||
    state.minConfidence > DEFAULT_URL_STATE.minConfidence ||
    state.search !== ""
  );
}

const FILTER_RESET_PATCH: Partial<UrlState> = {
  subdomain: null,
  tier: null,
  minConfidence: DEFAULT_URL_STATE.minConfidence,
  search: "",
};

const selectClasses =
  "h-8 rounded-md border border-border bg-surface-1 px-2 text-xs text-primary disabled:cursor-not-allowed disabled:opacity-60";

/** Accessible segmented toggle: real buttons with aria-pressed state. */
function ToggleGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: ReadonlyArray<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-col gap-1 text-xs text-secondary">
      <span aria-hidden="true">{label}</span>
      <div
        role="group"
        aria-label={label}
        className="flex h-8 items-center gap-0.5 rounded-md border border-border bg-surface-1 p-0.5"
      >
        {options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(option.value)}
              className={cn(
                "h-full rounded px-2.5 text-xs font-medium transition-colors duration-150",
                active
                  ? "bg-surface-2 text-primary"
                  : "text-secondary hover:text-primary",
              )}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Sticky filter bar (spec 19.2/19.3): domain, subdomain, geo level,
 * score layer, minimum confidence, tier, and search — all persisted in
 * the URL via lib/urlstate so every view is shareable.
 */
function FilterBar({
  state,
  update,
  subdomainOptions,
}: {
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
  subdomainOptions: string[];
}) {
  // Keep an out-of-dataset subdomain from a shared URL visible in the select.
  const options =
    state.subdomain !== null && !subdomainOptions.includes(state.subdomain)
      ? [...subdomainOptions, state.subdomain].sort()
      : subdomainOptions;

  return (
    <div className="z-30 rounded-lg border border-border bg-background/95 px-4 py-3 backdrop-blur lg:sticky lg:top-16">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
        <label className="flex flex-col gap-1 text-xs text-secondary">
          Domain
          {/* Single pilot domain; the select activates with expansion domains. */}
          <select
            value={DEFAULT_DOMAIN_ID}
            disabled
            title="Cloud and DevOps is the only pilot domain"
            className={selectClasses}
          >
            <option value={DEFAULT_DOMAIN_ID}>Cloud and DevOps</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-secondary">
          Subdomain
          <select
            value={state.subdomain ?? ""}
            onChange={(event) =>
              update({ subdomain: event.target.value || null })
            }
            className={selectClasses}
          >
            <option value="">All subdomains</option>
            {options.map((id) => (
              <option key={id} value={id}>
                {subdomainLabel(id)}
              </option>
            ))}
          </select>
        </label>

        <ToggleGroup
          label="Geographic level"
          options={GEO_LEVEL_OPTIONS}
          value={state.level}
          onChange={(level) => update({ level })}
        />

        <ToggleGroup
          label="Score layer"
          options={SCORE_LAYER_OPTIONS}
          value={state.layer}
          onChange={(layer) => update({ layer })}
        />

        <label className="flex flex-col gap-1 text-xs text-secondary">
          <span>
            Min confidence{" "}
            <span className="score-value text-primary">
              {Math.round(state.minConfidence)}
            </span>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={state.minConfidence}
            onChange={(event) =>
              update({ minConfidence: Number(event.target.value) })
            }
            aria-label="Minimum confidence"
            aria-valuetext={`Minimum confidence ${Math.round(state.minConfidence)} of 100`}
            className="h-8 w-32 accent-accent"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-secondary">
          Recommendation tier
          <select
            value={state.tier ?? ""}
            onChange={(event) =>
              update({
                tier: (event.target.value || null) as RecommendationTier | null,
              })
            }
            className={selectClasses}
          >
            <option value="">All tiers</option>
            {TIER_OPTIONS.map((tier) => (
              <option key={tier.value} value={tier.value}>
                {tier.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-secondary">
          Search locations
          <input
            type="search"
            value={state.search}
            onChange={(event) => update({ search: event.target.value })}
            placeholder="Name or country code…"
            className="h-8 w-44 rounded-md border border-border bg-surface-1 px-2 text-xs text-primary placeholder:text-secondary/60"
          />
        </label>

        {hasActiveFilters(state) ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => update(FILTER_RESET_PATCH)}
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
            Reset filters
          </Button>
        ) : null}
      </div>
    </div>
  );
}

/** Designed no-rows-match state with a reset action (spec 19 empty states). */
function NoMatchState({ onReset }: { onReset: () => void }) {
  return (
    <div
      role="status"
      className="flex h-full min-h-64 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-white/15 bg-surface-1 px-6 py-10 text-center"
    >
      <span
        aria-hidden="true"
        className="flex size-10 items-center justify-center rounded-full border border-accent/30 bg-accent/10"
      >
        <SearchX className="size-5 text-accent" />
      </span>
      <p className="max-w-xs text-sm font-medium text-primary">
        No locations match the current filters
      </p>
      <p className="max-w-xs text-xs leading-5 text-secondary">
        Lower the minimum confidence, clear the search, or reset every filter
        to see the full ranking again.
      </p>
      <Button variant="secondary" size="sm" onClick={onReset}>
        <RotateCcw aria-hidden="true" className="size-3.5" />
        Reset filters
      </Button>
    </div>
  );
}

/** Designed unsupported-domain state (spec 19 empty states). */
function UnsupportedDomainState({
  domain,
  onSwitch,
}: {
  domain: string;
  onSwitch: () => void;
}) {
  return (
    <div
      role="status"
      className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-white/15 bg-surface-1 px-6 py-14 text-center"
    >
      <span
        aria-hidden="true"
        className="flex size-10 items-center justify-center rounded-full border border-warning/30 bg-warning/10"
      >
        <TriangleAlert className="size-5 text-warning" />
      </span>
      <p className="max-w-md text-sm font-medium text-primary">
        The domain “{domain}” is not part of this dataset
      </p>
      <p className="max-w-md text-xs leading-5 text-secondary">
        The pilot covers Cloud and DevOps only. Expansion domains activate
        once their pipelines publish data.
      </p>
      <Button variant="secondary" size="sm" onClick={onSwitch}>
        Switch to Cloud and DevOps
      </Button>
    </div>
  );
}

/**
 * Score-breakdown panel for the selected geography (spec 19.2, panel
 * below the map): the five component ScoreBars plus headline scores,
 * counts, and a link to the full detail page.
 */
function ScoreBreakdownPanel({
  row,
  onOpenDetail,
  onClear,
}: {
  row: GeographicRankingRow;
  onOpenDetail: () => void;
  onClear: () => void;
}) {
  const components: Array<[string, number]> = [
    ["Expert supply", row.expertSupplyScore],
    ["Expert quality", row.expertQualityScore],
    ["Collaboration depth", row.collaborationDepthScore],
    [
      row.momentumProvisional ? "Momentum (provisional)" : "Momentum",
      row.momentumScore,
    ],
    ["Ecosystem breadth", row.ecosystemBreadthScore],
  ];
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">
            <span aria-hidden="true">{countryFlag(row.countryCode)}</span>{" "}
            {row.name}
          </CardTitle>
          <TierBadge tier={row.recommendationTier} />
          <ConfidenceBadge score={row.confidenceScore} />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="primary" size="sm" onClick={onOpenDetail}>
            Open detail page
            <ArrowUpRight aria-hidden="true" className="size-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onClear}>
            <X aria-hidden="true" className="size-3.5" />
            Clear selection
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-2.5">
          {components.map(([label, value]) => (
            <ScoreBar key={label} label={label} value={value} />
          ))}
          {row.momentumProvisional ? (
            <p className="text-xs leading-5 text-warning">
              Momentum was computed from an incomplete window and is
              provisional.
            </p>
          ) : null}
        </div>
        <dl className="grid grid-cols-2 content-start gap-3">
          <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
            <dt className="text-xs text-secondary">Opportunity</dt>
            <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
              {formatScore(row.opportunityScore)}
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
            <dt className="text-xs text-secondary">Rank</dt>
            <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
              #{row.rank}
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
            <dt className="text-xs text-secondary">Observable experts</dt>
            <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
              {formatCount(row.observableExpertCount)}
            </dd>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/50 px-3 py-2.5">
            <dt className="text-xs text-secondary">Qualified repositories</dt>
            <dd className="score-value mt-0.5 text-lg font-semibold text-primary">
              {formatCount(row.qualifiedRepoCount)}
            </dd>
          </div>
        </dl>
      </div>
    </Card>
  );
}

/**
 * Main explorer content once rankings are loaded: map, ranked rail, and
 * the score-breakdown panel. The rail's DataTable is the accessible text
 * alternative for the map, wired via aria-describedby.
 */
function ExplorerContent({
  rows,
  state,
  update,
}: {
  rows: GeographicRankingRow[];
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
}) {
  const navigate = useNavigate();
  const railId = useId();
  const selectedGeoId = state.selected[0] ?? null;

  const filteredRows = useMemo(() => applyFilters(rows, state), [rows, state]);

  const openDetail = useCallback(
    (geoId: string) => {
      void navigate(`/location/${encodeURIComponent(geoId)}`);
    },
    [navigate],
  );

  /* First interaction selects; a second one opens the detail route. */
  const handleSelect = useCallback(
    (geoId: string) => {
      if (geoId === selectedGeoId) {
        openDetail(geoId);
      } else {
        update({ selected: [geoId] });
      }
    },
    [selectedGeoId, openDetail, update],
  );

  const selectedRow = useMemo(
    () =>
      selectedGeoId !== null
        ? (rows.find((row) => row.geoId === selectedGeoId) ?? null)
        : null,
    [rows, selectedGeoId],
  );

  const columns = useMemo<Array<DataTableColumn<GeographicRankingRow>>>(
    () => [
      {
        key: "rank",
        header: "#",
        cell: (row) => row.rank,
        sortValue: (row) => row.rank,
        cellClassName: "score-value",
      },
      {
        key: "name",
        header: "Location",
        cell: (row) => {
          const selected = row.geoId === selectedGeoId;
          return (
            <button
              type="button"
              aria-pressed={selected}
              title={
                selected
                  ? "Selected — activate again to open the detail page"
                  : "Select this location on the map"
              }
              onClick={() => handleSelect(row.geoId)}
              className={cn(
                "inline-flex items-center gap-1.5 text-left font-medium hover:text-accent",
                selected ? "text-accent" : "text-primary",
              )}
            >
              <span aria-hidden="true">{countryFlag(row.countryCode)}</span>
              {row.name}
            </button>
          );
        },
        sortValue: (row) => row.name,
      },
      {
        key: "tier",
        header: "Tier",
        cell: (row) => <TierBadge tier={row.recommendationTier} />,
      },
      {
        key: "opportunity",
        header: "Opportunity",
        align: "right",
        cell: (row) => formatScore(row.opportunityScore),
        sortValue: (row) => row.opportunityScore,
        cellClassName: "score-value",
      },
      {
        key: "confidence",
        header: "Confidence",
        align: "right",
        cell: (row) => formatScore(row.confidenceScore),
        sortValue: (row) => row.confidenceScore,
        cellClassName: "score-value",
      },
      {
        key: "experts",
        header: "Experts",
        align: "right",
        cell: (row) => formatCount(row.observableExpertCount),
        sortValue: (row) => row.observableExpertCount,
        cellClassName: "score-value",
      },
      {
        key: "topSubdomain",
        header: "Top subdomain",
        cell: (row) =>
          row.topSubdomains.length > 0
            ? subdomainLabel(row.topSubdomains[0])
            : NO_VALUE,
      },
    ],
    [handleSelect, selectedGeoId],
  );

  return (
    <div className="space-y-6">
      {state.layer === "momentum" &&
      filteredRows.some((row) => row.momentumProvisional) ? (
        <p
          role="note"
          className="flex items-center gap-2 text-xs leading-5 text-warning"
        >
          <TriangleAlert aria-hidden="true" className="size-3.5 shrink-0" />
          Momentum is provisional for some locations — the dataset window is
          incomplete.
        </p>
      ) : null}

      {/* Desktop: 65% map / 35% ranked rail. Mobile: map above the list. */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]">
        <AtlasMap
          rows={filteredRows}
          layer={state.layer}
          level={state.level}
          selectedGeoId={selectedGeoId}
          onSelect={handleSelect}
          describedBy={railId}
        />

        <div id={railId} className="min-w-0">
          <h2 className="mb-2 text-sm font-semibold text-primary">
            Ranked locations
            <span className="score-value ml-2 font-normal text-secondary">
              {filteredRows.length} of {rows.length}
            </span>
          </h2>
          {filteredRows.length > 0 ? (
            <DataTable
              columns={columns}
              rows={filteredRows}
              rowKey={(row) => row.geoId}
              caption={`Ranked ${state.level === "country" ? "countries" : "cities"} for the ${SCORE_LAYER_LABELS[state.layer]} layer with the active filters — the accessible text alternative to the map.`}
              initialSort={{ key: "rank", direction: "asc" }}
              maxHeight={560}
            />
          ) : (
            <NoMatchState onReset={() => update(FILTER_RESET_PATCH)} />
          )}
        </div>
      </div>

      <Section
        title="Score breakdown"
        description="The five component scores behind the opportunity score for the selected location. Opportunity and confidence are always reported separately."
      >
        {selectedRow ? (
          <ScoreBreakdownPanel
            row={selectedRow}
            onOpenDetail={() => openDetail(selectedRow.geoId)}
            onClear={() => update({ selected: [] })}
          />
        ) : (
          <p className="flex items-center gap-2 rounded-lg border border-border bg-surface-1 px-4 py-6 text-xs leading-5 text-secondary">
            <MousePointerClick aria-hidden="true" className="size-4 shrink-0" />
            Select a location on the map or in the ranked table to see its
            score breakdown. A second interaction opens the full profile.
          </p>
        )}
      </Section>
    </div>
  );
}

export default function Explorer() {
  const [state, update] = useUrlState();

  /*
   * Only the active geographic level is fetched, so city rankings are
   * lazy-loaded on first toggle (spec 20, map requirements) and cached
   * by lib/data afterwards.
   */
  const level = state.level;
  const domain = state.domain;
  const rankingsState = useDataFile(
    useCallback(() => loadRankings(level, domain), [level, domain]),
  );

  const rows =
    rankingsState.status === "ok" ? rankingsState.data.rows : NO_ROWS;

  const subdomainOptions = useMemo(() => {
    const ids = new Set<string>();
    for (const row of rows) {
      for (const id of row.topSubdomains) {
        ids.add(id);
      }
    }
    return [...ids].sort();
  }, [rows]);

  const domainSupported = domain === DEFAULT_DOMAIN_ID;

  return (
    <PageContainer className="space-y-6">
      <PageHeader
        title="Geographic explorer"
        description="An interactive world map of ranked Cloud and DevOps talent locations, colored by the selected score layer, with confidence shown through opacity and dashed borders — never color alone. The ranked rail alongside is the accessible tabular alternative."
      />

      <FilterBar
        state={state}
        update={update}
        subdomainOptions={subdomainOptions}
      />

      {!domainSupported ? (
        <UnsupportedDomainState
          domain={domain}
          onSwitch={() => update({ domain: DEFAULT_DOMAIN_ID, subdomain: null })}
        />
      ) : (
        <DataGate
          state={rankingsState}
          skeleton={
            <div className="grid gap-6 lg:grid-cols-[minmax(0,65fr)_minmax(0,35fr)]">
              <Skeleton className="h-[420px] w-full lg:h-[600px]" />
              <Skeleton className="h-[420px] w-full lg:h-[600px]" />
            </div>
          }
          emptyDetail={
            level === "city"
              ? "City rankings have not been published for this dataset yet. Switch back to country level, or check again after the next pipeline run."
              : "The country choropleth, score layers, and ranked rail render from the published rankings files."
          }
        >
          {(rankings) => (
            <ExplorerContent rows={rankings.rows} state={state} update={update} />
          )}
        </DataGate>
      )}
    </PageContainer>
  );
}
