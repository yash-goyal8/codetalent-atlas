"""Contributor expert score (spec 16.2): 0-100 domain-specific evidence score.

``score_contributors`` emits one spec 9.7 row per (contributor, domain):

    Expert Score = 35% domain activity + 25% contribution quality
                 + 20% repository quality exposure + 10% continuity
                 + 10% collaboration

Bias safeguards (spec 16.2), all enforced here:

- **Followers are never used.** No follower field is read anywhere in this
  module (nor is the user-profile table an input at all).
- **Single-repository cap**: each repository's weighted event points are
  capped at the configured share (40%) of the contributor's uncapped domain
  total, and every downstream consumer of points (domain activity volume,
  contribution quality, exposure weights) uses the capped points.
- **Push-volume cap**: push events counted per contributor-repository pair
  are clipped at the configured maximum before any weighting.
- **Two meaningful active days**: contributors below the configured minimum
  are excluded from scoring entirely. Because spec 9.4 stores per-repository
  ``active_days`` (calendar overlap across repositories is unobservable), we
  use a provable lower bound on distinct active days: the maximum per-repo
  ``active_days``, or the number of distinct calendar dates among the
  contributor's ``first_seen``/``last_seen`` values, whichever is larger.
- **One-repository contributors marked**: ``qualified_repo_count == 1`` in
  the spec 9.7 output, plus an explicit ``one_repo`` diagnostic column.
- **Raw and weighted counts kept**: diagnostic columns ``raw_event_count``
  (unweighted event total) and ``weighted_event_points`` (config-weighted,
  push- and share-capped total) accompany every row.

The output therefore carries the spec 9.7 columns first, followed by the
three diagnostic columns above (a documented, additive extension).

Formula decisions (the spec names signals, not formulas):

- **Domain activity**: robust count scales (winsorize -> log1p -> min-max,
  within the domain population) of the capped weighted event points, the
  qualified repository count, and subdomain breadth (distinct subdomains of
  the contributor's qualified repositories, from spec 9.3 classification).
- **Contribution quality**: robust count scale of the same capped event-point
  mix (merged PRs authored weigh 5x per ``event_weights``, reviews 4, PRs
  opened 3, capped pushes 2, issues 1). With spec 9.4 inputs the observable
  evidence mix for domain activity's volume signal and contribution quality
  is identical; the two components still differ through domain activity's
  breadth signals. This is contribution-quality *evidence*, never a claim of
  intrinsic developer quality (spec 16.2).
- **Repository quality exposure**: capped-point-weighted mean of repository
  quality scores; the share cap bounds any one repository's influence. A
  contributor whose capped point total is zero gets uniform weights.
  "Qualified repository" means accepted by classification AND present in the
  repository score table.
- **Continuity**: months lower bound (analogous to the days bound above),
  percentile-rank recency of the latest activity vs ``window_end``, and the
  robust count scale of the first-to-last activity span in days.
- **Collaboration**: robust count scales of reviews submitted, pull-request
  participation (PRs opened + merged authored), and repository+organization
  breadth (qualified repo count + distinct owner count).

KNOWN DATA GAP (decision B-04): ``push_commit_count`` is structurally 0 for
the pilot and is never used; ``push_events`` is the push-volume signal.

Determinism: grouping, scaling, and output are sorted by
``(domain_id, actor_login)``; no wall clock is read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import cast

import polars as pl

from codetalent.config import ScoringConfig
from codetalent.schemas import LocationConfidence
from codetalent.scoring.normalization import scale_count, scale_rank, weighted_blend

#: Spec 9.7 columns, then the documented diagnostic extensions.
CONTRIBUTOR_SCORE_COLUMNS: tuple[str, ...] = (
    "actor_login",
    "domain_id",
    "expert_score",
    "domain_activity_score",
    "contribution_quality_score",
    "repository_quality_exposure_score",
    "continuity_score",
    "collaboration_score",
    "qualified_repo_count",
    "active_months",
    "country_code",
    "city",
    "location_confidence",
    "one_repo",
    "raw_event_count",
    "weighted_event_points",
)

_OUTPUT_SCHEMA: dict[str, type[pl.DataType]] = {
    "actor_login": pl.Utf8,
    "domain_id": pl.Utf8,
    "expert_score": pl.Float64,
    "domain_activity_score": pl.Float64,
    "contribution_quality_score": pl.Float64,
    "repository_quality_exposure_score": pl.Float64,
    "continuity_score": pl.Float64,
    "collaboration_score": pl.Float64,
    "qualified_repo_count": pl.Int64,
    "active_months": pl.Int64,
    "country_code": pl.Utf8,
    "city": pl.Utf8,
    "location_confidence": pl.Utf8,
    "one_repo": pl.Boolean,
    "raw_event_count": pl.Int64,
    "weighted_event_points": pl.Float64,
}


def repo_event_points(row: dict[str, object], scoring_config: ScoringConfig) -> float:
    """Weighted event points for one spec 9.4 (contributor, repository) row.

    Uses the configured ``event_weights`` with the push-volume cap applied.
    ``push_commit_count`` is never consulted (decision B-04). Shared with the
    geography engine so supply attribution uses identical arithmetic.
    """
    weights = scoring_config.event_weights
    push_cap = scoring_config.contributor_expert.caps.push_events_counted_max
    return (
        float(row["merged_pull_requests_authored"]) * weights.merged_pull_request  # type: ignore[arg-type]
        + float(row["reviews_submitted"]) * weights.pull_request_review  # type: ignore[arg-type]
        + float(row["pull_requests_opened"]) * weights.pull_request_opened  # type: ignore[arg-type]
        + min(float(row["push_events"]), float(push_cap)) * weights.push_event  # type: ignore[arg-type]
        + float(row["issues_opened"]) * weights.issue_opened  # type: ignore[arg-type]
        + float(row["issue_comments"]) * weights.issue_comment  # type: ignore[arg-type]
    )


def capped_repo_points(points: list[float], share_cap: float) -> list[float]:
    """Apply the spec 16.2 single-repository cap to per-repository points.

    Each repository's points are capped at ``share_cap`` of the contributor's
    **uncapped** total, so one repository can contribute at most the
    configured share of the point mass that feeds the score. The cap binds
    trivially for one-repository contributors (their single repository *is*
    100% of their activity); they are additionally marked via
    ``qualified_repo_count == 1`` / ``one_repo``.
    """
    total = sum(points)
    if total <= 0.0:
        return list(points)
    ceiling = share_cap * total
    return [min(value, ceiling) for value in points]


@dataclass
class _ContributorAggregate:
    """Per-(actor, domain) evidence collected before population scaling."""

    actor_login: str
    domain_id: str
    repo_names: list[str]
    capped_points: list[float]
    repo_qualities: list[float]
    raw_event_count: int
    quality_points_total: float
    reviews_total: int
    pr_participation: int
    subdomain_count: int
    org_count: int
    days_lower_bound: int
    months_lower_bound: int
    latest_activity: date
    span_days: int


def _distinct_count(values: list[object]) -> int:
    return len({str(value) for value in values})


def _aggregate(
    rows: list[dict[str, object]],
    subdomains_by_repo: dict[str, list[str]],
    quality_by_repo: dict[str, float],
    scoring_config: ScoringConfig,
) -> _ContributorAggregate:
    """Fold one contributor's qualified spec 9.4 rows into scoring evidence."""
    share_cap = scoring_config.contributor_expert.caps.single_repository_share
    rows = sorted(rows, key=lambda row: str(row["repo_name"]))

    points = [repo_event_points(row, scoring_config) for row in rows]
    capped = capped_repo_points(points, share_cap)

    firsts = [cast(date, row["first_seen"]) for row in rows]
    lasts = [cast(date, row["last_seen"]) for row in rows]
    seen_dates = {*firsts, *lasts}
    seen_months = {(d.year, d.month) for d in seen_dates}
    max_days = max(int(cast(int, row["active_days"])) for row in rows)
    max_months = max(int(cast(int, row["active_months"])) for row in rows)
    min_first = min(firsts)
    max_last = max(lasts)

    subdomains: set[str] = set()
    for row in rows:
        subdomains.update(subdomains_by_repo.get(str(row["repo_name"]), []))

    raw_event_count = sum(
        int(cast(int, row[field]))
        for row in rows
        for field in (
            "push_events",
            "pull_requests_opened",
            "merged_pull_requests_authored",
            "reviews_submitted",
            "issues_opened",
            "issue_comments",
        )
    )

    return _ContributorAggregate(
        actor_login=str(rows[0]["actor_login"]),
        domain_id=str(rows[0]["domain_id"]),
        repo_names=[str(row["repo_name"]) for row in rows],
        capped_points=capped,
        repo_qualities=[quality_by_repo[str(row["repo_name"])] for row in rows],
        raw_event_count=raw_event_count,
        quality_points_total=sum(capped),
        reviews_total=sum(int(cast(int, row["reviews_submitted"])) for row in rows),
        pr_participation=sum(
            int(cast(int, row["pull_requests_opened"]))
            + int(cast(int, row["merged_pull_requests_authored"]))
            for row in rows
        ),
        subdomain_count=len(subdomains),
        org_count=_distinct_count([str(row["repo_name"]).split("/", 1)[0] for row in rows]),
        days_lower_bound=max(max_days, len(seen_dates)),
        months_lower_bound=max(max_months, len(seen_months)),
        latest_activity=max_last,
        span_days=(max_last - min_first).days,
    )


def _exposure(aggregate: _ContributorAggregate) -> float:
    """Capped-point-weighted mean repository quality (already 0-100)."""
    total = sum(aggregate.capped_points)
    if total <= 0.0:
        return sum(aggregate.repo_qualities) / len(aggregate.repo_qualities)
    return sum(
        weight / total * quality
        for weight, quality in zip(aggregate.capped_points, aggregate.repo_qualities, strict=True)
    )


def score_contributors(
    activity_df: pl.DataFrame,
    classification_df: pl.DataFrame,
    repository_scores_df: pl.DataFrame,
    locations_df: pl.DataFrame,
    scoring_config: ScoringConfig,
    window_end: date,
) -> pl.DataFrame:
    """Score every eligible contributor per domain (spec 16.2 / 9.7).

    Restricts spec 9.4 activity to qualified repositories (classification
    accepted AND scored), enforces the meaningful-active-days minimum, scales
    every count signal within the domain population, and joins spec 9.6
    locations (absent contributors keep null country/city and an ``unusable``
    location confidence).
    """
    expert = scoring_config.contributor_expert
    winsor = expert.winsorization_percentile

    quality_by_repo: dict[str, float] = dict(
        zip(
            repository_scores_df.get_column("repo_name").to_list(),
            repository_scores_df.get_column("repository_quality_score").to_list(),
            strict=True,
        )
    )
    accepted = classification_df.filter(pl.col("classification_status") == "accepted")
    subdomains_by_repo: dict[str, list[str]] = {
        str(name): list(subs)
        for name, subs in zip(
            accepted.get_column("repo_name").to_list(),
            accepted.get_column("subdomains").to_list(),
            strict=True,
        )
    }
    qualified_repos = {name for name in subdomains_by_repo if name in quality_by_repo}

    qualified_activity = activity_df.filter(
        pl.col("repo_name").is_in(sorted(qualified_repos))
    ).sort("domain_id", "actor_login", "repo_name")

    aggregates: list[_ContributorAggregate] = []
    if qualified_activity.height > 0:
        for (_, _), group in qualified_activity.group_by(
            ["domain_id", "actor_login"], maintain_order=True
        ):
            aggregate = _aggregate(
                group.to_dicts(), subdomains_by_repo, quality_by_repo, scoring_config
            )
            if aggregate.days_lower_bound >= expert.minimums.meaningful_active_days:
                aggregates.append(aggregate)

    location_lookup: dict[str, tuple[str | None, str | None, str]] = {}
    for row in locations_df.select(
        "actor_login", "normalized_country_code", "normalized_city", "location_confidence"
    ).to_dicts():
        location_lookup[str(row["actor_login"])] = (
            row["normalized_country_code"],
            row["normalized_city"],
            str(row["location_confidence"]),
        )

    frames: list[pl.DataFrame] = []
    for domain_id in sorted({a.domain_id for a in aggregates}):
        domain = [a for a in aggregates if a.domain_id == domain_id]
        frames.append(
            _score_domain(domain, domain_id, location_lookup, scoring_config, winsor, window_end)
        )

    if not frames:
        return pl.DataFrame(schema=_OUTPUT_SCHEMA)
    return pl.concat(frames).sort("domain_id", "actor_login")


def _score_domain(
    domain: list[_ContributorAggregate],
    domain_id: str,
    location_lookup: dict[str, tuple[str | None, str | None, str]],
    scoring_config: ScoringConfig,
    winsor: float,
    window_end: date,
) -> pl.DataFrame:
    """Scale and blend one domain's population (signals are domain-relative)."""
    expert = scoring_config.contributor_expert
    signals = expert.signal_weights
    domain = sorted(domain, key=lambda a: a.actor_login)

    domain_activity = weighted_blend(
        {
            "event_points": scale_count([a.quality_points_total for a in domain], winsor),
            "qualified_repo_count": scale_count([float(len(a.repo_names)) for a in domain], winsor),
            "subdomain_breadth": scale_count([float(a.subdomain_count) for a in domain], winsor),
        },
        dict(signals.domain_activity),
    )
    contribution_quality = scale_count([a.quality_points_total for a in domain], winsor)
    exposure = [_exposure(a) for a in domain]
    continuity = weighted_blend(
        {
            "active_months": scale_count([float(a.months_lower_bound) for a in domain], winsor),
            "recency": scale_rank([-float((window_end - a.latest_activity).days) for a in domain]),
            "activity_span": scale_count([float(a.span_days) for a in domain], winsor),
        },
        dict(signals.continuity),
    )
    collaboration = weighted_blend(
        {
            "reviews": scale_count([float(a.reviews_total) for a in domain], winsor),
            "pull_request_participation": scale_count(
                [float(a.pr_participation) for a in domain], winsor
            ),
            "repo_org_breadth": scale_count(
                [float(len(a.repo_names) + a.org_count) for a in domain], winsor
            ),
        },
        dict(signals.collaboration),
    )

    components: dict[str, list[float]] = {
        "domain_activity": domain_activity,
        "contribution_quality": contribution_quality,
        "repository_quality_exposure": exposure,
        "continuity": continuity,
        "collaboration": collaboration,
    }
    component_weights = dict(expert.weights)
    final = weighted_blend(components, component_weights)

    # Spec 28 quality gates: components in 0-100, weighted sum matches final.
    for name, series in components.items():
        for value in series:
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} out of 0-100 bounds: {value}")
    for index, value in enumerate(final):
        expected = sum(component_weights[name] * components[name][index] for name in components)
        if abs(value - expected) > 1e-9:
            raise ValueError(
                f"weighted sum does not match expert score at row {index}: {expected} != {value}"
            )

    unlocated = (None, None, LocationConfidence.UNUSABLE.value)
    locations = [location_lookup.get(a.actor_login, unlocated) for a in domain]
    return pl.DataFrame(
        {
            "actor_login": [a.actor_login for a in domain],
            "domain_id": [domain_id] * len(domain),
            "expert_score": final,
            "domain_activity_score": domain_activity,
            "contribution_quality_score": contribution_quality,
            "repository_quality_exposure_score": exposure,
            "continuity_score": continuity,
            "collaboration_score": collaboration,
            "qualified_repo_count": [len(a.repo_names) for a in domain],
            "active_months": [a.months_lower_bound for a in domain],
            "country_code": [location[0] for location in locations],
            "city": [location[1] for location in locations],
            "location_confidence": [location[2] for location in locations],
            "one_repo": [len(a.repo_names) == 1 for a in domain],
            "raw_event_count": [a.raw_event_count for a in domain],
            "weighted_event_points": [a.quality_points_total for a in domain],
        },
        schema=_OUTPUT_SCHEMA,
    )
