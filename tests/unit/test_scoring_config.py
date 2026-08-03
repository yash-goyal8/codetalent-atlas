"""Milestone E scoring constants: every number lives in scoring.yaml (spec 8.3).

Also proves, for all three engines, that component weights are config-driven:
changing a weight in a modified copy of the configuration changes the output,
and weight groups that do not sum to 1.0 are rejected at load time.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from _scoring_fixtures import (
    SMALL_SAMPLE_OVERRIDES,
    WINDOW_END,
    activity_row,
    classification_row,
    contributor_row,
    location_row,
    metadata_row,
    repo_scores_frame,
    score_row,
    scoring_config,
)

from codetalent import config
from codetalent.scoring.contributor import score_contributors
from codetalent.scoring.geography import rank_geographies
from codetalent.scoring.repository import score_repositories


class TestNewScoringConstants:
    def test_repository_signal_weights_sum_to_one(self, config_dir: Path) -> None:
        signals = config.load_scoring(config_dir / "scoring.yaml").repository_quality.signal_weights
        for group in (
            signals.recent_activity,
            signals.contributor_diversity,
            signals.collaboration_quality,
            signals.technical_relevance,
            signals.repository_maturity,
        ):
            assert sum(dict(group).values()) == pytest.approx(1.0, abs=1e-9)

    def test_repository_thresholds_present(self, config_dir: Path) -> None:
        thresholds = config.load_scoring(config_dir / "scoring.yaml").repository_quality.thresholds
        assert thresholds.recurring_activity_min_months == 2
        assert thresholds.review_ratio_full_coverage == pytest.approx(1.0)
        assert thresholds.negative_evidence_full_penalty == 3

    def test_contributor_signal_weights_and_caps(self, config_dir: Path) -> None:
        expert = config.load_scoring(config_dir / "scoring.yaml").contributor_expert
        for group in (
            expert.signal_weights.domain_activity,
            expert.signal_weights.continuity,
            expert.signal_weights.collaboration,
        ):
            assert sum(dict(group).values()) == pytest.approx(1.0, abs=1e-9)
        assert expert.caps.push_events_counted_max == 100
        assert 0.0 < expert.winsorization_percentile < 1.0

    def test_geography_constants_present(self, config_dir: Path) -> None:
        geo = config.load_scoring(config_dir / "scoring.yaml").geography
        assert 0.0 < geo.winsorization_percentile < 1.0
        assert 0.0 < geo.supply_expert_score_cap <= 100.0
        assert 0.0 < geo.single_repository_supply_share_max <= 1.0
        assert geo.top_quartile_percentile == pytest.approx(0.75)
        assert geo.sample_saturation_multiple >= 1.0
        assert geo.recurring_contributor_min_months == 2
        assert geo.top_subdomains_count >= 1
        assert geo.momentum_direction_scores.down < geo.momentum_direction_scores.flat
        assert geo.momentum_direction_scores.flat < geo.momentum_direction_scores.up
        for group in (
            geo.signal_weights.expert_quality,
            geo.signal_weights.collaboration_depth,
            geo.signal_weights.ecosystem_breadth,
        ):
            assert sum(dict(group).values()) == pytest.approx(1.0, abs=1e-9)

    def test_signal_weight_group_not_summing_to_one_rejected(
        self, tmp_path: Path, config_dir: Path
    ) -> None:
        original = (config_dir / "scoring.yaml").read_text(encoding="utf-8")
        broken = original.replace("event_points: 0.50", "event_points: 0.60")
        path = tmp_path / "scoring.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(config.ConfigError, match=r"sum to 1\.0"):
            config.load_scoring(path)

    def test_geography_weight_group_not_summing_to_one_rejected(
        self, tmp_path: Path, config_dir: Path
    ) -> None:
        original = (config_dir / "scoring.yaml").read_text(encoding="utf-8")
        broken = original.replace("weighted_median: 0.70", "weighted_median: 0.80")
        path = tmp_path / "scoring.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(config.ConfigError, match=r"sum to 1\.0"):
            config.load_scoring(path)


def _repository_inputs() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    repos = [f"org{i}/repo{i}" for i in range(4)]
    activity = pl.DataFrame(
        [
            activity_row(name, releases=i, weighted_activity_score=100.0 * (i + 1))
            for i, name in enumerate(repos)
        ]
    )
    metadata = pl.DataFrame(
        [
            metadata_row(name, license_spdx_id=None if i == 0 else "MIT")
            for i, name in enumerate(repos)
        ]
    )
    classification = pl.DataFrame([classification_row(name) for name in repos])
    return activity, metadata, classification


class TestConfigWeightChangesMoveOutputs:
    """Property: change a configured component weight -> the score changes."""

    def test_repository_engine(self, config_dir: Path) -> None:
        activity, metadata, classification = _repository_inputs()
        base = score_repositories(
            activity, metadata, classification, scoring_config(config_dir), WINDOW_END
        )
        shifted_config = scoring_config(
            config_dir,
            {
                "repository_quality": {
                    "weights": {"recent_activity": 0.10, "repository_maturity": 0.30}
                }
            },
        )
        shifted = score_repositories(activity, metadata, classification, shifted_config, WINDOW_END)
        assert (
            base.get_column("repository_quality_score").to_list()
            != shifted.get_column("repository_quality_score").to_list()
        )

    def test_contributor_engine(self, config_dir: Path) -> None:
        repos = ["orga/repo1", "orgb/repo2"]
        classification = pl.DataFrame([classification_row(name) for name in repos])
        repo_scores = repo_scores_frame({"orga/repo1": 80.0, "orgb/repo2": 40.0})
        activity = pl.DataFrame(
            [
                contributor_row("alice", "orga/repo1"),
                contributor_row("alice", "orgb/repo2", reviews_submitted=0),
                contributor_row("bob", "orgb/repo2", merged_pull_requests_authored=20),
            ]
        )
        locations = pl.DataFrame([location_row("alice"), location_row("bob")])
        base = score_contributors(
            activity, classification, repo_scores, locations, scoring_config(config_dir), WINDOW_END
        )
        shifted_config = scoring_config(
            config_dir,
            {
                "contributor_expert": {
                    "weights": {"domain_activity": 0.15, "repository_quality_exposure": 0.40}
                }
            },
        )
        shifted = score_contributors(
            activity, classification, repo_scores, locations, shifted_config, WINDOW_END
        )
        assert (
            base.get_column("expert_score").to_list()
            != shifted.get_column("expert_score").to_list()
        )

    def test_geography_engine(self, config_dir: Path) -> None:
        repos = ["orga/repo1", "orgb/repo2"]
        classification = pl.DataFrame([classification_row(name) for name in repos])
        actors = [f"dev{i}" for i in range(6)]
        scores = pl.DataFrame(
            [score_row(actor, expert_score=40.0 + 10.0 * i) for i, actor in enumerate(actors)]
        )
        activity = pl.DataFrame(
            [contributor_row(actor, repos[i % 2]) for i, actor in enumerate(actors)]
        )
        locations = pl.DataFrame(
            [
                location_row(
                    actor,
                    **(
                        {}
                        if i < 4
                        else {
                            "normalized_country_code": "DE",
                            "normalized_country_name": "Germany",
                            "normalized_city": "Berlin",
                            "raw_location": "Berlin",
                        }
                    ),
                )
                for i, actor in enumerate(actors)
            ]
        )
        base_config = scoring_config(config_dir, SMALL_SAMPLE_OVERRIDES)
        base = rank_geographies(
            scores, activity, classification, locations, base_config, WINDOW_END
        )
        shifted_config = scoring_config(
            config_dir,
            {
                **SMALL_SAMPLE_OVERRIDES,
                "opportunity": {"weights": {"expert_supply": 0.15, "momentum": 0.30}},
            },
        )
        shifted = rank_geographies(
            scores, activity, classification, locations, shifted_config, WINDOW_END
        )
        assert (
            base.get_column("opportunity_score").to_list()
            != shifted.get_column("opportunity_score").to_list()
        )
        # Confidence weights are separate: opportunity stays put when only
        # confidence weights move.
        confidence_shifted_config = scoring_config(
            config_dir,
            {
                **SMALL_SAMPLE_OVERRIDES,
                "confidence": {
                    "weights": {"located_profile_coverage": 0.15, "sample_size_adequacy": 0.40}
                },
            },
        )
        confidence_shifted = rank_geographies(
            scores, activity, classification, locations, confidence_shifted_config, WINDOW_END
        )
        assert (
            base.get_column("opportunity_score").to_list()
            == confidence_shifted.get_column("opportunity_score").to_list()
        )
        assert (
            base.get_column("confidence_score").to_list()
            != confidence_shifted.get_column("confidence_score").to_list()
        )
