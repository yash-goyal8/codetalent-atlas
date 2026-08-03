"""Country/city opportunity, confidence, and tier assignment (spec section 17).

``rank_geographies`` emits one spec 9.8 row per (geo_level, geo_id, domain):

    Opportunity = 35% expert supply + 30% expert quality
                + 15% collaboration depth + 10% momentum + 10% ecosystem breadth
    Confidence  = 35% located profile coverage + 25% location certainty
                + 20% sample size adequacy + 10% repository diversity
                + 10% organization diversity

Opportunity and confidence are computed, stored, and ranked **separately** —
they are never merged into one opaque score. All weights, caps, percentiles,
minimum-sample rules, and tier thresholds come from ``config/scoring.yaml``.

Eligibility (spec 15, via :mod:`codetalent.locations.confidence`): country
rankings admit high + medium confidence country matches; city rankings admit
high-confidence city matches only.

Formula decisions (the spec names signals, not formulas):

- **Expert supply**: each contributor's supply weight is
  ``min(expert_score, supply_expert_score_cap) / 100`` — the elite cap keeps
  a few very high scores from replacing headcount. Supply is attributed to
  repositories proportionally to each contributor's capped event points, and
  one repository's attribution is capped at the configured share of the
  geography's weighted supply (spec 17 concentration safeguard). The capped
  total is then robustly log-scaled across geographies of the same level and
  domain. ``weighted_expert_count`` reports the *uncapped* elite-capped sum;
  ``observable_expert_count`` reports the raw headcount (raw and weighted
  counts are both shown, spec 17).
- **Expert quality**: supply-weighted **median** expert score blended with
  the top-quartile share (share of contributors at or above the domain- and
  level-wide ``top_quartile_percentile`` of expert scores). Never a mean.
- **Collaboration depth**: shares of multi-repository experts
  (``qualified_repo_count >= 2``), review participants (any review), and
  recurring contributors (active months at or above the configured minimum).
- **Momentum (pilot — PROVISIONAL)**: month-over-month direction only, per
  spec 17's three-month-pilot rule. A contributor counts as active in a month
  when any of their per-repository ``first_seen``/``last_seen`` intervals
  intersects it (an upper-bound proxy: spec 9.4 has no monthly series). The
  direction (latest window month vs the month before) maps to the configured
  up/flat/down scores. Treat every pilot momentum value as provisional; the
  twelve-month dataset replaces this with real three-month comparisons.
- **Ecosystem breadth**: robust count scales of qualified repositories,
  distinct organizations, and distinct subdomains active in the geography,
  plus a concentration term ``(1 - max organization share) * 100``.
- **Located profile coverage**: the domain-global share of scored
  contributors with a country-ranking-eligible location — identical for every
  geography of a domain, it measures how trustworthy the location layer
  itself is (a per-geography "coverage" would be 100% by construction).
- **Sample size adequacy**: mean of the smooth saturating ratios of the
  level's three minimum-sample counts (full marks at
  ``minimum * sample_saturation_multiple``).
- **Repository/organization diversity**: ``(1 - max share of the
  geography's weighted activity) * 100`` per dimension.

Concentration safeguards: any organization contributing more than the
configured ``concentration.organization_share_flag`` share of a geography's
weighted activity is flagged via the diagnostic columns
``org_concentration_share`` / ``org_concentration_flag`` (spec 17 requires a
concentration-risk indicator; spec 9.8 lacks a field for it, so these two
columns extend the schema — a documented, additive deviation).

Minimum sample rules: geographies below the configured minimums are tiered
``insufficient_data`` and never receive a normal rank. Because spec 9.8 types
``rank`` as an integer, gated rows are ranked *after* every ranked row
(opportunity descending, confidence descending, then ``geo_id``), so their
rank values continue the sequence while the ``insufficient_data`` tier marks
them as unranked for display purposes (documented decision).

``geo_id``: country rows use the ISO country code (e.g. ``US``); city rows
use ``<country>-<city-slug>`` with the city lowercased and spaces replaced by
hyphens (e.g. ``US-san-francisco``).

Determinism: all grouping and output ordering is stable (sorted by domain,
level, and final rank); no wall clock is read.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

import polars as pl

from codetalent.config import RecommendationTiers, ScoringConfig
from codetalent.locations.confidence import city_ranking_eligible, country_ranking_eligible
from codetalent.schemas import (
    GeoLevel,
    LocationConfidence,
    NormalizedLocation,
    RecommendationTier,
)
from codetalent.scoring.contributor import capped_repo_points, repo_event_points
from codetalent.scoring.normalization import (
    percentile_value,
    saturating_ratio,
    scale_count,
    weighted_blend,
    weighted_median,
)

#: Spec 9.8 columns, then the documented concentration-risk diagnostics.
GEOGRAPHIC_RANKING_COLUMNS: tuple[str, ...] = (
    "geo_level",
    "geo_id",
    "country_code",
    "city",
    "domain_id",
    "opportunity_score",
    "confidence_score",
    "expert_supply_score",
    "expert_quality_score",
    "collaboration_depth_score",
    "momentum_score",
    "ecosystem_breadth_score",
    "observable_expert_count",
    "weighted_expert_count",
    "qualified_repo_count",
    "organization_count",
    "multi_repo_expert_share",
    "located_profile_coverage",
    "high_confidence_location_share",
    "top_subdomains",
    "rank",
    "recommendation_tier",
    "org_concentration_share",
    "org_concentration_flag",
)

_OUTPUT_SCHEMA: dict[str, pl.DataType | type[pl.DataType]] = {
    "geo_level": pl.Utf8,
    "geo_id": pl.Utf8,
    "country_code": pl.Utf8,
    "city": pl.Utf8,
    "domain_id": pl.Utf8,
    "opportunity_score": pl.Float64,
    "confidence_score": pl.Float64,
    "expert_supply_score": pl.Float64,
    "expert_quality_score": pl.Float64,
    "collaboration_depth_score": pl.Float64,
    "momentum_score": pl.Float64,
    "ecosystem_breadth_score": pl.Float64,
    "observable_expert_count": pl.Int64,
    "weighted_expert_count": pl.Float64,
    "qualified_repo_count": pl.Int64,
    "organization_count": pl.Int64,
    "multi_repo_expert_share": pl.Float64,
    "located_profile_coverage": pl.Float64,
    "high_confidence_location_share": pl.Float64,
    "top_subdomains": pl.List(pl.Utf8),
    "rank": pl.Int64,
    "recommendation_tier": pl.Utf8,
    "org_concentration_share": pl.Float64,
    "org_concentration_flag": pl.Boolean,
}


def assign_tier(
    opportunity: float,
    confidence: float,
    samples_ok: bool,
    tiers: RecommendationTiers,
) -> RecommendationTier:
    """Spec 17 recommendation tier from configured thresholds.

    ``insufficient_data`` when the minimum-sample rule failed or confidence is
    below the configured floor — a high opportunity score with low confidence
    is never labeled a priority recommendation. Rows with adequate samples and
    confidence that reach neither priority nor promising fall to ``monitor``
    (the spec's monitor condition plus a documented fallback for the
    combination it leaves unnamed: low opportunity with high confidence).
    """
    if not samples_ok or confidence < tiers.insufficient_data.max_confidence:
        return RecommendationTier.INSUFFICIENT_DATA
    if (
        opportunity >= tiers.priority.min_opportunity
        and confidence >= tiers.priority.min_confidence
    ):
        return RecommendationTier.PRIORITY
    if (
        opportunity >= tiers.promising.min_opportunity
        and confidence >= tiers.promising.min_confidence
    ):
        return RecommendationTier.PROMISING
    return RecommendationTier.MONITOR


def city_geo_id(country_code: str, city: str) -> str:
    """Deterministic city geo id: ``<country>-<city-slug>`` (documented)."""
    return f"{country_code}-{city.lower().replace(' ', '-')}"


@dataclass
class _ActorEvidence:
    """One located contributor's per-domain evidence for geo aggregation."""

    actor_login: str
    expert_score: float
    qualified_repo_count: int
    active_months: int
    reviews_total: int = 0
    repo_points: dict[str, float] = field(default_factory=dict)
    intervals: list[tuple[date, date]] = field(default_factory=list)


@dataclass
class _GeoAggregate:
    """Raw per-geography evidence before cross-geography scaling."""

    country_code: str
    city: str | None
    actors: list[_ActorEvidence]
    high_confidence_count: int

    @property
    def repo_activity(self) -> dict[str, float]:
        totals: dict[str, float] = {}
        for actor in self.actors:
            for repo, points in actor.repo_points.items():
                totals[repo] = totals.get(repo, 0.0) + points
        return totals


@dataclass
class _GeoComputed:
    """One geography's fully computed raw signals, pre cross-geo scaling."""

    geo: _GeoAggregate
    observable: int
    weighted: float
    capped_supply: float
    expert_quality: float
    collaboration_depth: float
    momentum: float
    repo_count: int
    org_count: int
    subdomain_count: int
    max_repo_share: float
    max_org_share: float
    multi_repo_share: float
    top_subdomains: list[str]


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _active_in_month(actor: _ActorEvidence, bounds: tuple[date, date]) -> bool:
    start, end = bounds
    return any(first <= end and last >= start for first, last in actor.intervals)


def _capped_supply_total(geo: _GeoAggregate, share_cap: float, score_cap: float) -> float:
    """Weighted supply with the single-repository attribution cap applied."""
    supply_by_repo: dict[str, float] = {}
    total_supply = 0.0
    for actor in geo.actors:
        weight = min(actor.expert_score, score_cap) / 100.0
        total_supply += weight
        actor_points = sum(actor.repo_points.values())
        if actor_points <= 0.0:
            continue
        for repo, points in actor.repo_points.items():
            supply_by_repo[repo] = supply_by_repo.get(repo, 0.0) + weight * points / actor_points
    if not supply_by_repo:
        return total_supply
    unattributed = total_supply - sum(supply_by_repo.values())
    ceiling = share_cap * total_supply
    return unattributed + sum(min(value, ceiling) for value in supply_by_repo.values())


def _max_share(totals: dict[str, float]) -> float:
    grand_total = sum(totals.values())
    if grand_total <= 0.0:
        return 0.0
    return max(totals.values()) / grand_total


def rank_geographies(
    contributor_scores_df: pl.DataFrame,
    activity_df: pl.DataFrame,
    classification_df: pl.DataFrame,
    locations_df: pl.DataFrame,
    scoring_config: ScoringConfig,
    window_end: date,
) -> pl.DataFrame:
    """Rank every observable geography per domain and level (spec 17 / 9.8)."""
    accepted = classification_df.filter(pl.col("classification_status") == "accepted")
    subdomains_by_repo: dict[str, list[str]] = {
        str(name): list(subs)
        for name, subs in zip(
            accepted.get_column("repo_name").to_list(),
            accepted.get_column("subdomains").to_list(),
            strict=True,
        )
    }

    locations = [
        NormalizedLocation.model_validate(row)
        for row in locations_df.sort("actor_login").to_dicts()
    ]
    country_geo: dict[str, str] = {}
    city_geo: dict[str, tuple[str, str]] = {}
    confidence_by_actor: dict[str, LocationConfidence] = {}
    for row in locations:
        confidence_by_actor[row.actor_login] = row.location_confidence
        if country_ranking_eligible(row):
            assert row.normalized_country_code is not None
            country_geo[row.actor_login] = row.normalized_country_code
        if city_ranking_eligible(row):
            assert row.normalized_country_code is not None
            assert row.normalized_city is not None
            city_geo[row.actor_login] = (row.normalized_country_code, row.normalized_city)

    frames: list[pl.DataFrame] = []
    domain_ids = sorted(set(contributor_scores_df.get_column("domain_id").to_list()))
    for domain_id in domain_ids:
        frames.extend(
            _rank_domain(
                domain_id=domain_id,
                scores=contributor_scores_df.filter(pl.col("domain_id") == domain_id),
                activity=activity_df.filter(
                    (pl.col("domain_id") == domain_id)
                    & pl.col("repo_name").is_in(sorted(subdomains_by_repo))
                ),
                subdomains_by_repo=subdomains_by_repo,
                country_geo=country_geo,
                city_geo=city_geo,
                confidence_by_actor=confidence_by_actor,
                scoring_config=scoring_config,
                window_end=window_end,
            )
        )
    if not frames:
        return pl.DataFrame(schema=_OUTPUT_SCHEMA)
    return pl.concat(frames).sort("domain_id", "geo_level", "rank")


def _actor_evidence(
    scores: pl.DataFrame,
    activity: pl.DataFrame,
    scoring_config: ScoringConfig,
) -> dict[str, _ActorEvidence]:
    """Fold per-domain score rows and activity into per-actor evidence."""
    share_cap = scoring_config.contributor_expert.caps.single_repository_share
    evidence: dict[str, _ActorEvidence] = {}
    for row in scores.sort("actor_login").to_dicts():
        evidence[str(row["actor_login"])] = _ActorEvidence(
            actor_login=str(row["actor_login"]),
            expert_score=float(row["expert_score"]),
            qualified_repo_count=int(row["qualified_repo_count"]),
            active_months=int(row["active_months"]),
        )
    for row in activity.sort("actor_login", "repo_name").to_dicts():
        actor = evidence.get(str(row["actor_login"]))
        if actor is None:  # not scored (e.g. failed the active-days minimum)
            continue
        actor.reviews_total += int(row["reviews_submitted"])
        actor.repo_points[str(row["repo_name"])] = repo_event_points(row, scoring_config)
        actor.intervals.append((row["first_seen"], row["last_seen"]))
    for actor in evidence.values():
        repos = sorted(actor.repo_points)
        capped = capped_repo_points([actor.repo_points[repo] for repo in repos], share_cap)
        actor.repo_points = dict(zip(repos, capped, strict=True))
    return evidence


def _rank_domain(
    *,
    domain_id: str,
    scores: pl.DataFrame,
    activity: pl.DataFrame,
    subdomains_by_repo: dict[str, list[str]],
    country_geo: dict[str, str],
    city_geo: dict[str, tuple[str, str]],
    confidence_by_actor: dict[str, LocationConfidence],
    scoring_config: ScoringConfig,
    window_end: date,
) -> list[pl.DataFrame]:
    evidence = _actor_evidence(scores, activity, scoring_config)
    total_scored = len(evidence)
    located_eligible = sum(1 for actor in evidence if actor in country_geo)
    coverage = located_eligible / total_scored if total_scored else 0.0

    frames: list[pl.DataFrame] = []
    for level in (GeoLevel.COUNTRY, GeoLevel.CITY):
        geos: dict[tuple[str, str | None], _GeoAggregate] = {}
        for actor_login, actor in sorted(evidence.items()):
            if level is GeoLevel.COUNTRY:
                country = country_geo.get(actor_login)
                if country is None:
                    continue
                key: tuple[str, str | None] = (country, None)
            else:
                located = city_geo.get(actor_login)
                if located is None:
                    continue
                key = located
            geo = geos.get(key)
            if geo is None:
                geo = _GeoAggregate(
                    country_code=key[0], city=key[1], actors=[], high_confidence_count=0
                )
                geos[key] = geo
            geo.actors.append(actor)
            if confidence_by_actor.get(actor_login) is LocationConfidence.HIGH:
                geo.high_confidence_count += 1
        if geos:
            frames.append(
                _score_level(
                    domain_id=domain_id,
                    level=level,
                    geos=[geos[key] for key in sorted(geos, key=lambda k: (k[0], k[1] or ""))],
                    subdomains_by_repo=subdomains_by_repo,
                    coverage=coverage,
                    scoring_config=scoring_config,
                    window_end=window_end,
                )
            )
    return frames


def _score_level(
    *,
    domain_id: str,
    level: GeoLevel,
    geos: list[_GeoAggregate],
    subdomains_by_repo: dict[str, list[str]],
    coverage: float,
    scoring_config: ScoringConfig,
    window_end: date,
) -> pl.DataFrame:
    geo_cfg = scoring_config.geography
    winsor = geo_cfg.winsorization_percentile
    signals = geo_cfg.signal_weights
    tiers = scoring_config.tiers
    org_flag_share = scoring_config.concentration.organization_share_flag

    all_scores = [actor.expert_score for geo in geos for actor in geo.actors]
    quartile_threshold = percentile_value(all_scores, geo_cfg.top_quartile_percentile)

    latest_bounds = _month_bounds(window_end.year, window_end.month)
    previous_bounds = _month_bounds(*_previous_month(window_end.year, window_end.month))

    per_geo: list[_GeoComputed] = []
    for geo in geos:
        actors = geo.actors
        count = len(actors)
        supply_weights = [
            min(actor.expert_score, geo_cfg.supply_expert_score_cap) / 100.0 for actor in actors
        ]
        weighted_count = sum(supply_weights)
        capped_supply = _capped_supply_total(
            geo, geo_cfg.single_repository_supply_share_max, geo_cfg.supply_expert_score_cap
        )

        repo_activity = geo.repo_activity
        org_activity: dict[str, float] = {}
        subdomain_activity: dict[str, float] = {}
        for repo, points in repo_activity.items():
            org = repo.split("/", 1)[0]
            org_activity[org] = org_activity.get(org, 0.0) + points
            for subdomain in subdomains_by_repo.get(repo, []):
                subdomain_activity[subdomain] = subdomain_activity.get(subdomain, 0.0) + points
        max_repo_share = _max_share(repo_activity)
        max_org_share = _max_share(org_activity)

        expert_quality = weighted_blend(
            {
                "weighted_median": [
                    weighted_median([actor.expert_score for actor in actors], supply_weights)
                    if weighted_count > 0
                    else 0.0
                ],
                "top_quartile_share": [
                    sum(1 for actor in actors if actor.expert_score >= quartile_threshold)
                    / count
                    * 100.0
                ],
            },
            dict(signals.expert_quality),
        )[0]

        collaboration_depth = weighted_blend(
            {
                "multi_repo_share": [
                    sum(1 for actor in actors if actor.qualified_repo_count >= 2) / count * 100.0
                ],
                "review_participation": [
                    sum(1 for actor in actors if actor.reviews_total > 0) / count * 100.0
                ],
                "recurring_share": [
                    sum(
                        1
                        for actor in actors
                        if actor.active_months >= geo_cfg.recurring_contributor_min_months
                    )
                    / count
                    * 100.0
                ],
            },
            dict(signals.collaboration_depth),
        )[0]

        latest_active = sum(1 for actor in actors if _active_in_month(actor, latest_bounds))
        previous_active = sum(1 for actor in actors if _active_in_month(actor, previous_bounds))
        directions = geo_cfg.momentum_direction_scores
        if latest_active > previous_active:
            momentum = directions.up
        elif latest_active < previous_active:
            momentum = directions.down
        else:
            momentum = directions.flat

        top_subdomains = [
            name
            for name, _ in sorted(subdomain_activity.items(), key=lambda item: (-item[1], item[0]))[
                : geo_cfg.top_subdomains_count
            ]
        ]

        per_geo.append(
            _GeoComputed(
                geo=geo,
                observable=count,
                weighted=weighted_count,
                capped_supply=capped_supply,
                expert_quality=expert_quality,
                collaboration_depth=collaboration_depth,
                momentum=momentum,
                repo_count=len(repo_activity),
                org_count=len(org_activity),
                subdomain_count=len(subdomain_activity),
                max_repo_share=max_repo_share,
                max_org_share=max_org_share,
                multi_repo_share=sum(1 for actor in actors if actor.qualified_repo_count >= 2)
                / count,
                top_subdomains=top_subdomains,
            )
        )

    expert_supply = scale_count([g.capped_supply for g in per_geo], winsor)
    ecosystem_breadth = weighted_blend(
        {
            "qualified_repos": scale_count([float(g.repo_count) for g in per_geo], winsor),
            "organizations": scale_count([float(g.org_count) for g in per_geo], winsor),
            "subdomain_breadth": scale_count([float(g.subdomain_count) for g in per_geo], winsor),
            "low_concentration": [(1.0 - g.max_org_share) * 100.0 for g in per_geo],
        },
        dict(signals.ecosystem_breadth),
    )

    opportunity_components: dict[str, list[float]] = {
        "expert_supply": expert_supply,
        "expert_quality": [g.expert_quality for g in per_geo],
        "collaboration_depth": [g.collaboration_depth for g in per_geo],
        "momentum": [g.momentum for g in per_geo],
        "ecosystem_breadth": ecosystem_breadth,
    }
    opportunity_weights = dict(scoring_config.opportunity.weights)
    opportunity = weighted_blend(opportunity_components, opportunity_weights)

    minimums = scoring_config.minimum_samples
    confidence_rows: list[dict[str, float]] = []
    samples_ok_flags: list[bool] = []
    for entry in per_geo:
        observable = entry.observable
        repo_count = entry.repo_count
        org_count = entry.org_count
        if level is GeoLevel.COUNTRY:
            contributor_minimum = minimums.country.located_contributors
            repo_minimum = minimums.country.qualified_repositories
            org_minimum = minimums.country.organizations
            contributor_count = observable
        else:
            contributor_minimum = minimums.city.high_confidence_located_contributors
            repo_minimum = minimums.city.qualified_repositories
            org_minimum = minimums.city.organizations
            contributor_count = entry.geo.high_confidence_count
        samples_ok_flags.append(
            contributor_count >= contributor_minimum
            and repo_count >= repo_minimum
            and org_count >= org_minimum
        )
        adequacy = (
            saturating_ratio(
                contributor_count, contributor_minimum, geo_cfg.sample_saturation_multiple
            )
            + saturating_ratio(repo_count, repo_minimum, geo_cfg.sample_saturation_multiple)
            + saturating_ratio(org_count, org_minimum, geo_cfg.sample_saturation_multiple)
        ) / 3.0
        high_share = entry.geo.high_confidence_count / observable if observable else 0.0
        confidence_rows.append(
            {
                "located_profile_coverage": coverage * 100.0,
                "location_certainty": high_share * 100.0,
                "sample_size_adequacy": adequacy * 100.0,
                "repository_diversity": (1.0 - entry.max_repo_share) * 100.0,
                "organization_diversity": (1.0 - entry.max_org_share) * 100.0,
            }
        )

    confidence_components: dict[str, list[float]] = {
        name: [row[name] for row in confidence_rows]
        for name in (
            "located_profile_coverage",
            "location_certainty",
            "sample_size_adequacy",
            "repository_diversity",
            "organization_diversity",
        )
    }
    confidence_weights = dict(scoring_config.confidence.weights)
    confidence = weighted_blend(confidence_components, confidence_weights)

    # Spec 28 quality gates: weighted sums match the final scores.
    for index in range(len(per_geo)):
        expected_opportunity = sum(
            opportunity_weights[name] * opportunity_components[name][index]
            for name in opportunity_components
        )
        expected_confidence = sum(
            confidence_weights[name] * confidence_components[name][index]
            for name in confidence_components
        )
        if abs(opportunity[index] - expected_opportunity) > 1e-9:
            raise ValueError(f"opportunity weighted sum mismatch at row {index}")
        if abs(confidence[index] - expected_confidence) > 1e-9:
            raise ValueError(f"confidence weighted sum mismatch at row {index}")

    tiers_assigned = [
        assign_tier(opportunity[i], confidence[i], samples_ok_flags[i], tiers)
        for i in range(len(per_geo))
    ]

    def geo_identifier(index: int) -> str:
        geo = per_geo[index].geo
        if level is GeoLevel.COUNTRY:
            return geo.country_code
        assert geo.city is not None
        return city_geo_id(geo.country_code, geo.city)

    # Ranked rows first (opportunity desc, confidence desc, geo_id asc); the
    # insufficient_data rows continue the rank sequence afterwards (documented).
    order = sorted(
        range(len(per_geo)),
        key=lambda i: (
            tiers_assigned[i] is RecommendationTier.INSUFFICIENT_DATA,
            -opportunity[i],
            -confidence[i],
            geo_identifier(i),
        ),
    )
    rank_by_index = {index: position + 1 for position, index in enumerate(order)}

    rows: list[dict[str, object]] = []
    for index in order:
        entry = per_geo[index]
        geo = entry.geo
        rows.append(
            {
                "geo_level": level.value,
                "geo_id": geo_identifier(index),
                "country_code": geo.country_code,
                "city": geo.city,
                "domain_id": domain_id,
                "opportunity_score": opportunity[index],
                "confidence_score": confidence[index],
                "expert_supply_score": expert_supply[index],
                "expert_quality_score": entry.expert_quality,
                "collaboration_depth_score": entry.collaboration_depth,
                "momentum_score": entry.momentum,
                "ecosystem_breadth_score": ecosystem_breadth[index],
                "observable_expert_count": entry.observable,
                "weighted_expert_count": entry.weighted,
                "qualified_repo_count": entry.repo_count,
                "organization_count": entry.org_count,
                "multi_repo_expert_share": entry.multi_repo_share,
                "located_profile_coverage": coverage,
                "high_confidence_location_share": (geo.high_confidence_count / entry.observable),
                "top_subdomains": list(entry.top_subdomains),
                "rank": rank_by_index[index],
                "recommendation_tier": tiers_assigned[index].value,
                "org_concentration_share": entry.max_org_share,
                "org_concentration_flag": entry.max_org_share > org_flag_share,
            }
        )
    return pl.DataFrame(rows, schema=_OUTPUT_SCHEMA)
