"""Repository quality engine tests on hand-built synthetic fixtures (spec 16.1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest
from _scoring_fixtures import (
    WINDOW_END,
    activity_row,
    classification_row,
    metadata_row,
    scoring_config,
)

from codetalent.config import ScoringConfig
from codetalent.scoring.repository import REPOSITORY_SCORE_COLUMNS, score_repositories

MEGA = "megacorp/monolith"
OTHERS = [f"org{i}/repo{i}" for i in range(5)]
REPOS = [MEGA, *OTHERS]


def _six_repo_fixture() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Six accepted repos: one mega repository plus five ordinary ones."""
    activity_rows = [
        activity_row(
            MEGA,
            unique_human_contributors=5000,
            active_days=92,
            active_months=3,
            merged_pull_requests=20000,
            reviews_submitted=30000,
            pull_requests_opened=25000,
            issue_comments=50000,
            releases=40,
            weighted_activity_score=10_000_000.0,
        )
    ]
    for index, name in enumerate(OTHERS):
        activity_rows.append(
            activity_row(
                name,
                unique_human_contributors=5 + 3 * index,
                active_days=20 + 10 * index,
                merged_pull_requests=5 + 5 * index,
                reviews_submitted=4 + 6 * index,
                pull_requests_opened=8 + 4 * index,
                issue_comments=10 + 8 * index,
                releases=index,
                weighted_activity_score=100.0 * (index + 1),
                last_seen=date(2026, 7, 10 + index * 4),
            )
        )
    metadata = pl.DataFrame([metadata_row(name) for name in REPOS])
    classification = pl.DataFrame(
        [
            classification_row(name, classification_score=4.0 + index)
            for index, name in enumerate(REPOS)
        ]
    )
    return pl.DataFrame(activity_rows), metadata, classification


@pytest.fixture
def cfg(config_dir: Path) -> ScoringConfig:
    return scoring_config(config_dir)


class TestScoreRepositories:
    def test_output_contract(self, cfg: ScoringConfig) -> None:
        frame = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        assert frame.columns == list(REPOSITORY_SCORE_COLUMNS)
        assert frame.height == 6
        assert frame.get_column("repo_name").to_list() == sorted(REPOS)

    def test_all_scores_bounded(self, cfg: ScoringConfig) -> None:
        frame = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        for column in REPOSITORY_SCORE_COLUMNS[1:]:
            values = frame.get_column(column).to_list()
            assert all(0.0 <= value <= 100.0 for value in values), column

    def test_weighted_sum_matches_final(self, cfg: ScoringConfig) -> None:
        frame = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        weights = dict(cfg.repository_quality.weights)
        for row in frame.to_dicts():
            expected = (
                weights["recent_activity"] * row["recent_activity_score"]
                + weights["contributor_diversity"] * row["contributor_diversity_score"]
                + weights["collaboration_quality"] * row["collaboration_quality_score"]
                + weights["technical_relevance"] * row["technical_relevance_score"]
                + weights["repository_maturity"] * row["repository_maturity_score"]
            )
            assert row["repository_quality_score"] == pytest.approx(expected, abs=1e-9)

    def test_mega_repo_does_not_crush_others(self, cfg: ScoringConfig) -> None:
        """Winsorization + log1p keep ordinary repos distinguishable (spec 16.1)."""
        frame = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        by_name = {row["repo_name"]: row for row in frame.to_dicts()}
        other_scores = [by_name[name]["repository_quality_score"] for name in OTHERS]
        other_recent = [by_name[name]["recent_activity_score"] for name in OTHERS]
        # Ordinary repositories stay meaningfully above zero...
        assert max(other_scores) > 40.0
        assert max(other_recent) > 30.0
        # ...and remain distinguishable from each other instead of being
        # compressed into a band near 0 by the mega repository's magnitudes.
        assert max(other_recent) - min(other_recent) > 10.0

    def test_only_accepted_repositories_scored(self, cfg: ScoringConfig) -> None:
        activity, metadata, classification = _six_repo_fixture()
        classification = pl.DataFrame(
            [
                classification_row(MEGA),
                classification_row(OTHERS[0], classification_status="rejected"),
                classification_row(OTHERS[1], classification_status="borderline"),
                classification_row(OTHERS[2]),
            ]
        )
        frame = score_repositories(activity, metadata, classification, cfg, WINDOW_END)
        assert frame.get_column("repo_name").to_list() == sorted([MEGA, OTHERS[2]])

    def test_empty_inputs_give_empty_frame(self, cfg: ScoringConfig) -> None:
        activity, metadata, _ = _six_repo_fixture()
        empty_classification = pl.DataFrame([classification_row("x/y")]).filter(pl.lit(False))
        frame = score_repositories(activity, metadata, empty_classification, cfg, WINDOW_END)
        assert frame.height == 0
        assert frame.columns == list(REPOSITORY_SCORE_COLUMNS)

    def test_null_content_signal_counts_as_zero_evidence_not_penalty(
        self, cfg: ScoringConfig
    ) -> None:
        """has_ci=None (never fetched) scores identically to an observed False."""
        names = ["a/none", "b/false", "c/true"]
        activity = pl.DataFrame([activity_row(name) for name in names])
        metadata = pl.DataFrame(
            [
                metadata_row("a/none", has_ci=None),
                metadata_row("b/false", has_ci=False),
                metadata_row("c/true", has_ci=True),
            ]
        )
        classification = pl.DataFrame([classification_row(name) for name in names])
        frame = score_repositories(activity, metadata, classification, cfg, WINDOW_END)
        by_name = {row["repo_name"]: row["repository_maturity_score"] for row in frame.to_dicts()}
        assert by_name["a/none"] == by_name["b/false"]
        assert by_name["c/true"] > by_name["a/none"]

    def test_recency_orders_recent_above_stale(self, cfg: ScoringConfig) -> None:
        names = ["a/fresh", "b/stale", "c/mid"]
        activity = pl.DataFrame(
            [
                activity_row("a/fresh", last_seen=date(2026, 7, 30)),
                activity_row("b/stale", last_seen=date(2026, 5, 20)),
                activity_row("c/mid", last_seen=date(2026, 6, 25)),
            ]
        )
        metadata = pl.DataFrame([metadata_row(name) for name in names])
        classification = pl.DataFrame([classification_row(name) for name in names])
        frame = score_repositories(activity, metadata, classification, cfg, WINDOW_END)
        by_name = {row["repo_name"]: row["recent_activity_score"] for row in frame.to_dicts()}
        assert by_name["a/fresh"] > by_name["c/mid"] > by_name["b/stale"]

    def test_deterministic_and_byte_identical(self, cfg: ScoringConfig, tmp_path: Path) -> None:
        first = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        second = score_repositories(*_six_repo_fixture(), cfg, WINDOW_END)
        assert first.equals(second)
        path_a = tmp_path / "a.parquet"
        path_b = tmp_path / "b.parquet"
        first.write_parquet(path_a)
        second.write_parquet(path_b)
        assert path_a.read_bytes() == path_b.read_bytes()
