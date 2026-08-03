"""Repository quality score (spec 16.1): 0-100 from configured component weights.

``score_repositories`` scores every classification-**accepted** repository:

    Repository Quality = 30% recent activity + 25% contributor diversity
                       + 20% collaboration quality + 15% technical relevance
                       + 10% repository maturity

All component and sub-signal weights, thresholds, and the winsorization
percentile come from ``config/scoring.yaml`` (spec 8.3). Count-like signals
use the robust recipe from :mod:`codetalent.scoring.normalization`
(winsorize at the configured percentile -> ``log1p`` -> min-max into 0-100),
so a single mega repository cannot crush every other repository to ~0.
Pure-ordering signals (recency) use percentile ranks.

Formula decisions (the spec names signals, not exact formulas — each choice
below is a documented decision):

- **Recent activity**: robust count scales of ``active_months``,
  ``active_days``, ``releases`` and ``weighted_activity_score``; recency is
  the percentile rank of ``-(window_end - last_seen).days`` (more recent =
  higher), which needs no extra decay constant.
- **Contributor diversity**: robust count scale of
  ``unique_human_contributors``; the one-actor concentration penalty is
  ``(1 - single_actor_event_share) * 100``; the spec's *recurring contributor
  share* is proxied by whether the repository was active in at least the
  configured ``recurring_activity_min_months`` distinct months (spec 9.1
  carries no per-contributor recurrence at repository grain). The spec's *new
  contributor share* signal is unobservable from spec 9.1/9.2 inputs and is
  therefore omitted (recorded as a data-gap decision, not fabricated).
- **Collaboration quality**: robust count scales of merged PRs and reviews; a
  review-coverage ratio ``min(reviews / max(pull_requests_opened, 1),
  full_coverage) / full_coverage * 100``; the spec's *multi-person issue
  participation* is proxied by the robust count scale of ``issue_comments``
  (per-issue participant counts are not in spec 9.1).
- **Technical relevance**: percentile rank of ``classification_score`` (all
  scored repositories are accepted, so magnitudes are compressed and ordering
  is the robust signal); robust count scale of total evidence items (topics +
  terms + files); a negative-evidence subscore ``(1 - min(n_negative /
  negative_evidence_full_penalty, 1)) * 100``.
- **Repository maturity**: binary 0/100 evidence for a recognized license
  (non-null ``license_spdx_id``), CI, tests, and governance docs
  (CONTRIBUTING or CODE_OF_CONDUCT), plus the robust count scale of
  ``release_count``. Null content signals (``has_ci`` etc. never fetched)
  count as 0 evidence — absence of evidence, never an extra penalty; they
  contribute exactly as much as an observed False.

KNOWN DATA GAP (decision B-04): ``push_commit_count`` is structurally 0 for
the pilot window and is never used as a signal here.

Determinism: rows are processed and emitted sorted by ``repo_name``; no wall
clock is read (``window_end`` is an explicit argument).
"""

from __future__ import annotations

from datetime import date

import polars as pl

from codetalent.config import ScoringConfig
from codetalent.scoring.normalization import scale_count, scale_rank, weighted_blend

#: Output column contract: key, final score, then the five component columns.
REPOSITORY_SCORE_COLUMNS: tuple[str, ...] = (
    "repo_name",
    "repository_quality_score",
    "recent_activity_score",
    "contributor_diversity_score",
    "collaboration_quality_score",
    "technical_relevance_score",
    "repository_maturity_score",
)

_OUTPUT_SCHEMA: dict[str, type[pl.DataType]] = {
    "repo_name": pl.Utf8,
    "repository_quality_score": pl.Float64,
    "recent_activity_score": pl.Float64,
    "contributor_diversity_score": pl.Float64,
    "collaboration_quality_score": pl.Float64,
    "technical_relevance_score": pl.Float64,
    "repository_maturity_score": pl.Float64,
}


def _assert_bounded(name: str, series: list[float]) -> None:
    for value in series:
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"{name} out of 0-100 bounds: {value}")


def score_repositories(
    activity_df: pl.DataFrame,
    metadata_df: pl.DataFrame,
    classification_df: pl.DataFrame,
    scoring_config: ScoringConfig,
    window_end: date,
) -> pl.DataFrame:
    """Score all classification-accepted repositories (spec 16.1).

    Joins spec 9.3 accepted rows with their spec 9.1 activity and spec 9.2
    metadata (inner joins: an accepted repository missing either input cannot
    be scored honestly and is excluded rather than fabricated). Returns a
    frame with :data:`REPOSITORY_SCORE_COLUMNS`, sorted by ``repo_name``.
    """
    quality = scoring_config.repository_quality
    winsor = quality.winsorization_percentile
    signals = quality.signal_weights
    thresholds = quality.thresholds

    accepted = (
        classification_df.filter(pl.col("classification_status") == "accepted")
        .select(
            "repo_name",
            "classification_score",
            "evidence_topics",
            "evidence_terms",
            "evidence_files",
            "negative_evidence",
        )
        .join(
            activity_df.select(
                "repo_name",
                "active_months",
                "active_days",
                "releases",
                "weighted_activity_score",
                "last_seen",
                "unique_human_contributors",
                "single_actor_event_share",
                "merged_pull_requests",
                "reviews_submitted",
                "pull_requests_opened",
                "issue_comments",
            ),
            on="repo_name",
            how="inner",
        )
        .join(
            metadata_df.select(
                "repo_name",
                "license_spdx_id",
                "release_count",
                "has_ci",
                "has_tests_signal",
                "has_contributing",
                "has_code_of_conduct",
            ),
            on="repo_name",
            how="inner",
        )
        .sort("repo_name")
    )
    if accepted.height == 0:
        return pl.DataFrame(schema=_OUTPUT_SCHEMA)

    rows = accepted.to_dicts()

    # --- Recent activity ----------------------------------------------------
    recency_raw = [-float((window_end - row["last_seen"]).days) for row in rows]
    recent_activity = weighted_blend(
        {
            "active_months": scale_count([float(r["active_months"]) for r in rows], winsor),
            "active_days": scale_count([float(r["active_days"]) for r in rows], winsor),
            "recency": scale_rank(recency_raw),
            "releases": scale_count([float(r["releases"]) for r in rows], winsor),
            "weighted_activity": scale_count(
                [float(r["weighted_activity_score"]) for r in rows], winsor
            ),
        },
        dict(signals.recent_activity),
    )

    # --- Contributor diversity ----------------------------------------------
    contributor_diversity = weighted_blend(
        {
            "unique_contributors": scale_count(
                [float(r["unique_human_contributors"]) for r in rows], winsor
            ),
            "low_concentration": [
                (1.0 - float(r["single_actor_event_share"])) * 100.0 for r in rows
            ],
            "recurring_activity": [
                100.0 if r["active_months"] >= thresholds.recurring_activity_min_months else 0.0
                for r in rows
            ],
        },
        dict(signals.contributor_diversity),
    )

    # --- Collaboration quality ----------------------------------------------
    full = thresholds.review_ratio_full_coverage
    review_ratio = [
        min(float(r["reviews_submitted"]) / max(float(r["pull_requests_opened"]), 1.0), full)
        / full
        * 100.0
        for r in rows
    ]
    collaboration_quality = weighted_blend(
        {
            "merged_pull_requests": scale_count(
                [float(r["merged_pull_requests"]) for r in rows], winsor
            ),
            "reviews": scale_count([float(r["reviews_submitted"]) for r in rows], winsor),
            "review_to_pr_ratio": review_ratio,
            "issue_participation": scale_count([float(r["issue_comments"]) for r in rows], winsor),
        },
        dict(signals.collaboration_quality),
    )

    # --- Technical relevance ------------------------------------------------
    evidence_counts = [
        float(len(r["evidence_topics"]) + len(r["evidence_terms"]) + len(r["evidence_files"]))
        for r in rows
    ]
    full_penalty = thresholds.negative_evidence_full_penalty
    negative_absence = [
        (1.0 - min(len(r["negative_evidence"]) / full_penalty, 1.0)) * 100.0 for r in rows
    ]
    technical_relevance = weighted_blend(
        {
            "classification_score": scale_rank([float(r["classification_score"]) for r in rows]),
            "evidence_breadth": scale_count(evidence_counts, winsor),
            "negative_evidence_absence": negative_absence,
        },
        dict(signals.technical_relevance),
    )

    # --- Repository maturity ------------------------------------------------
    repository_maturity = weighted_blend(
        {
            "recognized_license": [
                100.0 if r["license_spdx_id"] is not None else 0.0 for r in rows
            ],
            "releases": scale_count([float(r["release_count"]) for r in rows], winsor),
            # Null content signals were never fetched: 0 evidence, not a penalty.
            "ci_signal": [100.0 if r["has_ci"] is True else 0.0 for r in rows],
            "tests_signal": [100.0 if r["has_tests_signal"] is True else 0.0 for r in rows],
            "governance_docs": [
                100.0
                if (r["has_contributing"] is True or r["has_code_of_conduct"] is True)
                else 0.0
                for r in rows
            ],
        },
        dict(signals.repository_maturity),
    )

    components: dict[str, list[float]] = {
        "recent_activity": recent_activity,
        "contributor_diversity": contributor_diversity,
        "collaboration_quality": collaboration_quality,
        "technical_relevance": technical_relevance,
        "repository_maturity": repository_maturity,
    }
    final = weighted_blend(components, dict(quality.weights))

    # Spec 28 quality gates: components in 0-100, weighted sum matches final.
    for name, series in components.items():
        _assert_bounded(name, series)
    _assert_bounded("repository_quality_score", final)
    component_weights = dict(quality.weights)
    for index, value in enumerate(final):
        expected = sum(component_weights[name] * components[name][index] for name in components)
        if abs(value - expected) > 1e-9:
            raise ValueError(
                f"weighted sum does not match final score at row {index}: {expected} != {value}"
            )

    return pl.DataFrame(
        {
            "repo_name": [r["repo_name"] for r in rows],
            "repository_quality_score": final,
            "recent_activity_score": recent_activity,
            "contributor_diversity_score": contributor_diversity,
            "collaboration_quality_score": collaboration_quality,
            "technical_relevance_score": technical_relevance,
            "repository_maturity_score": repository_maturity,
        },
        schema=_OUTPUT_SCHEMA,
    )
