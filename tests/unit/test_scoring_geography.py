"""Geography engine tests: gating, tiers, separation, median, determinism (spec 17)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest
from _scoring_fixtures import (
    SMALL_SAMPLE_OVERRIDES,
    WINDOW_END,
    classification_row,
    contributor_row,
    location_row,
    score_row,
    scoring_config,
)

from codetalent.config import ScoringConfig
from codetalent.schemas import RecommendationTier
from codetalent.scoring.geography import (
    GEOGRAPHIC_RANKING_COLUMNS,
    assign_tier,
    city_geo_id,
    rank_geographies,
)

REPOS = {
    "orga/r1": ["infrastructure_as_code"],
    "orgb/r2": ["containers_orchestration"],
    "orgc/r3": ["infrastructure_as_code", "sre_reliability"],
    "orgd/r4": ["observability_monitoring"],
}


def _classification() -> pl.DataFrame:
    return pl.DataFrame([classification_row(name, subdomains=subs) for name, subs in REPOS.items()])


def _us_location(actor: str) -> dict[str, object]:
    return location_row(actor)


def _de_location(actor: str) -> dict[str, object]:
    return location_row(
        actor,
        raw_location="Germany",
        normalized_country_code="DE",
        normalized_country_name="Germany",
        normalized_city=None,
        location_level="country",
        location_confidence="medium",
        normalization_method="parsed_country",
    )


def _br_location(actor: str) -> dict[str, object]:
    return location_row(
        actor,
        raw_location="Sao Paulo, Brazil",
        normalized_country_code="BR",
        normalized_country_name="Brazil",
        normalized_city="Sao Paulo",
    )


def _three_country_fixture() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """US (6 high-city experts) > DE (4 medium-country) > BR (2, below gates)."""
    scores: list[dict[str, object]] = []
    activity: list[dict[str, object]] = []
    locations: list[dict[str, object]] = []
    for index in range(6):
        actor = f"us{index}"
        scores.append(score_row(actor, expert_score=65.0 + 5.0 * index))
        activity.append(contributor_row(actor, "orga/r1", merged_pull_requests_authored=8))
        activity.append(contributor_row(actor, "orgb/r2"))
        locations.append(_us_location(actor))
    for index in range(4):
        actor = f"de{index}"
        scores.append(
            score_row(
                actor,
                expert_score=45.0 + 5.0 * index,
                country_code="DE",
                city=None,
                location_confidence="medium",
            )
        )
        activity.append(contributor_row(actor, "orgc/r3"))
        activity.append(contributor_row(actor, "orgd/r4"))
        locations.append(_de_location(actor))
    for index in range(2):
        actor = f"br{index}"
        scores.append(
            score_row(
                actor,
                expert_score=80.0,
                country_code="BR",
                city="Sao Paulo",
                qualified_repo_count=1,
                one_repo=True,
            )
        )
        activity.append(contributor_row(actor, "orgc/r3"))
        locations.append(_br_location(actor))
    return pl.DataFrame(scores), pl.DataFrame(activity), pl.DataFrame(locations)


@pytest.fixture
def cfg(config_dir: Path) -> ScoringConfig:
    return scoring_config(config_dir, SMALL_SAMPLE_OVERRIDES)


class TestAssignTier:
    @pytest.mark.parametrize(
        ("opportunity", "confidence", "samples_ok", "expected"),
        [
            (75.0, 70.0, True, RecommendationTier.PRIORITY),
            (74.9, 70.0, True, RecommendationTier.PROMISING),
            (75.0, 69.9, True, RecommendationTier.PROMISING),
            (60.0, 60.0, True, RecommendationTier.PROMISING),
            (59.9, 60.0, True, RecommendationTier.MONITOR),
            (60.0, 59.9, True, RecommendationTier.MONITOR),
            (45.0, 50.0, True, RecommendationTier.MONITOR),
            (44.9, 50.0, True, RecommendationTier.MONITOR),  # confidence in band
            (44.9, 44.9, True, RecommendationTier.INSUFFICIENT_DATA),
            (90.0, 44.9, True, RecommendationTier.INSUFFICIENT_DATA),
            (30.0, 90.0, True, RecommendationTier.MONITOR),  # documented fallback
            (90.0, 90.0, False, RecommendationTier.INSUFFICIENT_DATA),  # gate wins
        ],
    )
    def test_matrix(
        self,
        config_dir: Path,
        opportunity: float,
        confidence: float,
        samples_ok: bool,
        expected: RecommendationTier,
    ) -> None:
        tiers = scoring_config(config_dir).tiers
        assert assign_tier(opportunity, confidence, samples_ok, tiers) is expected

    def test_high_opportunity_low_confidence_is_never_priority(self, config_dir: Path) -> None:
        tiers = scoring_config(config_dir).tiers
        for confidence in (0.0, 30.0, 44.9, 45.0, 60.0, 69.9):
            assert assign_tier(99.0, confidence, True, tiers) is not RecommendationTier.PRIORITY


class TestThreeCountrySnapshot:
    def test_expected_ranks_and_tiers(self, cfg: ScoringConfig) -> None:
        scores, activity, locations = _three_country_fixture()
        frame = rank_geographies(scores, activity, _classification(), locations, cfg, WINDOW_END)
        assert frame.columns == list(GEOGRAPHIC_RANKING_COLUMNS)
        countries = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "country").to_dicts()
        }
        assert set(countries) == {"US", "DE", "BR"}
        assert countries["US"]["rank"] == 1
        assert countries["DE"]["rank"] == 2
        assert countries["BR"]["rank"] == 3
        assert countries["US"]["recommendation_tier"] != "insufficient_data"
        assert countries["DE"]["recommendation_tier"] != "insufficient_data"
        # BR fails the (lowered) minimum sample rules: 2 < 3 contributors.
        assert countries["BR"]["recommendation_tier"] == "insufficient_data"
        assert countries["US"]["opportunity_score"] > countries["DE"]["opportunity_score"]

        cities = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "city").to_dicts()
        }
        # DE actors are medium confidence: country-eligible, never city-eligible.
        assert set(cities) == {"US-seattle", "BR-sao-paulo"}
        assert cities["US-seattle"]["rank"] == 1
        assert cities["BR-sao-paulo"]["rank"] == 2
        assert cities["BR-sao-paulo"]["recommendation_tier"] == "insufficient_data"

    def test_counts_and_shares(self, cfg: ScoringConfig) -> None:
        scores, activity, locations = _three_country_fixture()
        frame = rank_geographies(scores, activity, _classification(), locations, cfg, WINDOW_END)
        countries = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "country").to_dicts()
        }
        us = countries["US"]
        assert us["observable_expert_count"] == 6
        assert 0.0 < us["weighted_expert_count"] < 6.0  # elite-capped weights
        assert us["qualified_repo_count"] == 2
        assert us["organization_count"] == 2
        assert us["high_confidence_location_share"] == pytest.approx(1.0)
        assert countries["DE"]["high_confidence_location_share"] == pytest.approx(0.0)
        # All 12 scored contributors are located -> full coverage everywhere.
        assert us["located_profile_coverage"] == pytest.approx(1.0)

    def test_min_sample_gate_withholds_normal_rank(self, cfg: ScoringConfig) -> None:
        scores, activity, locations = _three_country_fixture()
        frame = rank_geographies(scores, activity, _classification(), locations, cfg, WINDOW_END)
        for level in ("country", "city"):
            rows = frame.filter(pl.col("geo_level") == level).to_dicts()
            ranks = [row["rank"] for row in rows]
            assert sorted(ranks) == list(range(1, len(rows) + 1))
            # Every insufficient_data rank comes after every ranked row.
            gated = [r["rank"] for r in rows if r["recommendation_tier"] == "insufficient_data"]
            ranked = [r["rank"] for r in rows if r["recommendation_tier"] != "insufficient_data"]
            assert all(g > max(ranked) for g in gated)

    def test_deterministic_and_byte_identical(self, cfg: ScoringConfig, tmp_path: Path) -> None:
        first = rank_geographies(
            *(lambda t: (t[0], t[1], _classification(), t[2]))(_three_country_fixture()),
            cfg,
            WINDOW_END,
        )
        second = rank_geographies(
            *(lambda t: (t[0], t[1], _classification(), t[2]))(_three_country_fixture()),
            cfg,
            WINDOW_END,
        )
        assert first.equals(second)
        path_a = tmp_path / "a.parquet"
        path_b = tmp_path / "b.parquet"
        first.write_parquet(path_a)
        second.write_parquet(path_b)
        assert path_a.read_bytes() == path_b.read_bytes()


class TestOpportunityConfidenceSeparation:
    def test_location_coverage_moves_confidence_not_opportunity(self, cfg: ScoringConfig) -> None:
        scores, activity, locations = _three_country_fixture()
        base = rank_geographies(scores, activity, _classification(), locations, cfg, WINDOW_END)
        # Add scored-but-unlocated contributors: coverage drops, geographies
        # keep the same members.
        extra_scores = pl.concat(
            [
                scores,
                pl.DataFrame(
                    [
                        score_row(
                            f"ghost{i}",
                            country_code=None,
                            city=None,
                            location_confidence="unusable",
                        )
                        for i in range(6)
                    ]
                ),
            ]
        )
        extra_activity = pl.concat(
            [activity, pl.DataFrame([contributor_row(f"ghost{i}", "orga/r1") for i in range(6)])]
        )
        lowered = rank_geographies(
            extra_scores, extra_activity, _classification(), locations, cfg, WINDOW_END
        )
        base_countries = base.filter(pl.col("geo_level") == "country").sort("geo_id")
        lowered_countries = lowered.filter(pl.col("geo_level") == "country").sort("geo_id")
        assert (
            base_countries.get_column("opportunity_score").to_list()
            == lowered_countries.get_column("opportunity_score").to_list()
        )
        for before, after in zip(
            base_countries.get_column("confidence_score").to_list(),
            lowered_countries.get_column("confidence_score").to_list(),
            strict=True,
        ):
            assert after < before
        assert lowered_countries.get_column("located_profile_coverage").to_list() == (
            [pytest.approx(12 / 18)] * 3
        )


class TestExpertQualityUsesMedianNotMean:
    def test_outlier_case(self, cfg: ScoringConfig) -> None:
        """B's mean (47.5) beats A's (45): a mean-based score would rank B first.

        The supply-weighted median says A=45, B=30, and the expert quality
        component must equal the exact median blend, not the mean blend.
        """
        scores_rows: list[dict[str, object]] = []
        activity_rows: list[dict[str, object]] = []
        locations_rows: list[dict[str, object]] = []
        for index in range(4):
            actor = f"a{index}"
            scores_rows.append(score_row(actor, expert_score=45.0))
            activity_rows.append(contributor_row(actor, "orga/r1"))
            activity_rows.append(contributor_row(actor, "orgb/r2"))
            locations_rows.append(_us_location(actor))
        for index, score in enumerate([30.0, 30.0, 30.0, 100.0]):
            actor = f"b{index}"
            scores_rows.append(
                score_row(actor, expert_score=score, country_code="BR", city="Sao Paulo")
            )
            activity_rows.append(contributor_row(actor, "orgc/r3"))
            activity_rows.append(contributor_row(actor, "orgd/r4"))
            locations_rows.append(_br_location(actor))
        frame = rank_geographies(
            pl.DataFrame(scores_rows),
            pl.DataFrame(activity_rows),
            _classification(),
            pl.DataFrame(locations_rows),
            cfg,
            WINDOW_END,
        )
        countries = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "country").to_dicts()
        }
        weights = dict(cfg.geography.signal_weights.expert_quality)
        # Top-quartile threshold over all 8 scores is 45 -> A share 100%, B 25%.
        expected_a = weights["weighted_median"] * 45.0 + weights["top_quartile_share"] * 100.0
        expected_b = weights["weighted_median"] * 30.0 + weights["top_quartile_share"] * 25.0
        assert countries["US"]["expert_quality_score"] == pytest.approx(expected_a)
        assert countries["BR"]["expert_quality_score"] == pytest.approx(expected_b)
        assert countries["US"]["expert_quality_score"] > countries["BR"]["expert_quality_score"]


class TestConcentration:
    def test_dominant_organization_flagged(self, cfg: ScoringConfig) -> None:
        # US activity: one org holds ~all weighted activity -> flag. DE spread
        # across two orgs evenly -> 50% share still > 20% -> also flagged; use
        # six orgs for the unflagged case.
        scores_rows: list[dict[str, object]] = []
        activity_rows: list[dict[str, object]] = []
        locations_rows: list[dict[str, object]] = []
        for index in range(4):
            actor = f"us{index}"
            scores_rows.append(score_row(actor))
            activity_rows.append(
                contributor_row(actor, "orga/r1", merged_pull_requests_authored=50)
            )
            locations_rows.append(_us_location(actor))
        spread_repos = [f"org{code}/spread{code}" for code in "abcdef"]
        for index in range(6):
            actor = f"de{index}"
            scores_rows.append(
                score_row(actor, country_code="DE", city=None, location_confidence="medium")
            )
            activity_rows.append(contributor_row(actor, spread_repos[index]))
            locations_rows.append(_de_location(actor))
        classification = pl.DataFrame(
            [classification_row(name) for name in [*REPOS, *spread_repos]]
        )
        frame = rank_geographies(
            pl.DataFrame(scores_rows),
            pl.DataFrame(activity_rows),
            classification,
            pl.DataFrame(locations_rows),
            cfg,
            WINDOW_END,
        )
        countries = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "country").to_dicts()
        }
        assert countries["US"]["org_concentration_share"] == pytest.approx(1.0)
        assert countries["US"]["org_concentration_flag"] is True
        assert countries["DE"]["org_concentration_share"] == pytest.approx(1 / 6)
        assert countries["DE"]["org_concentration_flag"] is False


class TestMomentum:
    def test_direction_scores_are_provisional_config_values(self, cfg: ScoringConfig) -> None:
        directions = cfg.geography.momentum_direction_scores
        scores_rows: list[dict[str, object]] = []
        activity_rows: list[dict[str, object]] = []
        locations_rows: list[dict[str, object]] = []

        def add(actor: str, country_fn: object, first: date, last: date) -> None:
            location = country_fn(actor)  # type: ignore[operator]
            scores_rows.append(
                score_row(
                    actor,
                    country_code=location["normalized_country_code"],
                    city=location["normalized_city"],
                    location_confidence=location["location_confidence"],
                )
            )
            activity_rows.append(
                contributor_row(actor, "orga/r1", first_seen=first, last_seen=last)
            )
            locations_rows.append(location)

        for index in range(3):
            # US: activity only in July (latest month) -> up.
            add(f"us{index}", _us_location, date(2026, 7, 2), date(2026, 7, 20))
            # DE: activity ended in June -> down.
            add(f"de{index}", _de_location, date(2026, 5, 5), date(2026, 6, 15))
            # BR: spans June and July -> flat.
            add(f"br{index}", _br_location, date(2026, 6, 5), date(2026, 7, 20))
        frame = rank_geographies(
            pl.DataFrame(scores_rows),
            pl.DataFrame(activity_rows),
            _classification(),
            pl.DataFrame(locations_rows),
            cfg,
            WINDOW_END,
        )
        countries = {
            row["geo_id"]: row for row in frame.filter(pl.col("geo_level") == "country").to_dicts()
        }
        assert countries["US"]["momentum_score"] == pytest.approx(directions.up)
        assert countries["DE"]["momentum_score"] == pytest.approx(directions.down)
        assert countries["BR"]["momentum_score"] == pytest.approx(directions.flat)


class TestTopSubdomains:
    def test_ordered_by_weighted_activity(self, cfg: ScoringConfig) -> None:
        # Per actor: orga/r1 (iac) carries heavy activity, orgb/r2
        # (containers) light activity, orgc/r3 (iac + sre) minimal activity.
        # Weighted subdomain activity: iac (r1 + r3) > containers (r2) > sre.
        light = {
            "merged_pull_requests_authored": 0,
            "pull_requests_opened": 0,
            "reviews_submitted": 0,
            "push_events": 5,
        }
        minimal = {
            "merged_pull_requests_authored": 0,
            "pull_requests_opened": 0,
            "reviews_submitted": 0,
            "push_events": 0,
            "issues_opened": 0,
            "issue_comments": 1,
        }
        scores_rows: list[dict[str, object]] = []
        activity_rows: list[dict[str, object]] = []
        locations_rows: list[dict[str, object]] = []
        for index in range(3):
            actor = f"us{index}"
            scores_rows.append(score_row(actor))
            activity_rows.append(contributor_row(actor, "orga/r1"))
            activity_rows.append(contributor_row(actor, "orgb/r2", **light))
            activity_rows.append(contributor_row(actor, "orgc/r3", **minimal))
            locations_rows.append(_us_location(actor))
        frame = rank_geographies(
            pl.DataFrame(scores_rows),
            pl.DataFrame(activity_rows),
            _classification(),
            pl.DataFrame(locations_rows),
            cfg,
            WINDOW_END,
        )
        us = frame.filter(
            (pl.col("geo_level") == "country") & (pl.col("geo_id") == "US")
        ).to_dicts()[0]
        assert us["top_subdomains"] == [
            "infrastructure_as_code",
            "containers_orchestration",
            "sre_reliability",
        ]


class TestGeoIdentifiers:
    def test_city_geo_id_slug(self) -> None:
        assert city_geo_id("US", "San Francisco") == "US-san-francisco"
        assert city_geo_id("BR", "Sao Paulo") == "BR-sao-paulo"

    def test_empty_scores_give_empty_frame(self, cfg: ScoringConfig) -> None:
        empty_scores = pl.DataFrame([score_row("x")]).filter(pl.lit(False))
        empty_activity = pl.DataFrame([contributor_row("x", "orga/r1")]).filter(pl.lit(False))
        empty_locations = pl.DataFrame([location_row("x")]).filter(pl.lit(False))
        frame = rank_geographies(
            empty_scores, empty_activity, _classification(), empty_locations, cfg, WINDOW_END
        )
        assert frame.height == 0
        assert frame.columns == list(GEOGRAPHIC_RANKING_COLUMNS)
