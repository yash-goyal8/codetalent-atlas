"""Contributor expert engine tests: every spec 16.2 safeguard individually (spec 16.2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest
from _scoring_fixtures import (
    WINDOW_END,
    classification_row,
    contributor_row,
    location_row,
    repo_scores_frame,
    scoring_config,
)

from codetalent.config import ScoringConfig
from codetalent.scoring.contributor import (
    CONTRIBUTOR_SCORE_COLUMNS,
    capped_repo_points,
    score_contributors,
)

REPOS = ["orga/repo1", "orgb/repo2", "orgc/repo3"]


def _classification() -> pl.DataFrame:
    return pl.DataFrame(
        [
            classification_row(REPOS[0], subdomains=["infrastructure_as_code"]),
            classification_row(REPOS[1], subdomains=["containers_orchestration"]),
            classification_row(REPOS[2], subdomains=["infrastructure_as_code", "sre_reliability"]),
        ]
    )


def _repo_scores() -> pl.DataFrame:
    return repo_scores_frame({REPOS[0]: 90.0, REPOS[1]: 50.0, REPOS[2]: 20.0})


def _locations(actors: list[str]) -> pl.DataFrame:
    if not actors:  # 0-row frame that keeps the spec 9.6 columns
        return pl.DataFrame([location_row("placeholder")]).filter(pl.lit(False))
    return pl.DataFrame([location_row(actor) for actor in actors])


@pytest.fixture
def cfg(config_dir: Path) -> ScoringConfig:
    return scoring_config(config_dir)


def _score(
    cfg: ScoringConfig,
    activity_rows: list[dict[str, object]],
    locations: pl.DataFrame | None = None,
) -> pl.DataFrame:
    activity = pl.DataFrame(activity_rows)
    located = (
        locations
        if locations is not None
        else _locations(sorted({str(row["actor_login"]) for row in activity_rows}))
    )
    return score_contributors(activity, _classification(), _repo_scores(), located, cfg, WINDOW_END)


class TestFollowersNeverUsed:
    def test_no_scoring_module_references_the_followers_column(self, repo_root: Path) -> None:
        for module in sorted((repo_root / "src" / "codetalent" / "scoring").glob("*.py")):
            source = module.read_text(encoding="utf-8")
            assert "followers_count" not in source, module.name

    def test_inputs_carry_no_followers_column(self, cfg: ScoringConfig) -> None:
        # None of the four engine inputs has a followers column, and scoring
        # succeeds without one — the profile table is not even an input.
        rows = [contributor_row("alice", REPOS[0]), contributor_row("alice", REPOS[1])]
        activity = pl.DataFrame(rows)
        locations = _locations(["alice"])
        for frame in (activity, _classification(), _repo_scores(), locations):
            assert all("follower" not in column for column in frame.columns)
        assert _score(cfg, rows).height == 1


class TestSingleRepositoryCap:
    def test_cap_binds_on_a_dominant_repository(self, cfg: ScoringConfig) -> None:
        """90/10 point split collapses to 40/10 capped; 50/50 becomes 40/40."""
        merged_weight = cfg.event_weights.merged_pull_request
        zero = dict.fromkeys(
            [
                "push_events",
                "pull_requests_opened",
                "reviews_submitted",
                "issues_opened",
                "issue_comments",
            ],
            0,
        )
        rows = [
            contributor_row("dominant", REPOS[0], merged_pull_requests_authored=18, **zero),
            contributor_row("dominant", REPOS[1], merged_pull_requests_authored=2, **zero),
            contributor_row("balanced", REPOS[0], merged_pull_requests_authored=10, **zero),
            contributor_row("balanced", REPOS[1], merged_pull_requests_authored=10, **zero),
        ]
        frame = _score(cfg, rows)
        points = dict(
            zip(
                frame.get_column("actor_login").to_list(),
                frame.get_column("weighted_event_points").to_list(),
                strict=True,
            )
        )
        # Uncapped totals are both 20 * merged weight; the 40% share cap
        # (config) clips the dominant repository to 40% of that total.
        total = 20.0 * merged_weight
        cap = cfg.contributor_expert.caps.single_repository_share
        assert points["dominant"] == pytest.approx(cap * total + 2.0 * merged_weight)
        assert points["balanced"] == pytest.approx(2 * cap * total)
        assert points["dominant"] < points["balanced"]

    def test_capped_repo_points_helper(self) -> None:
        assert capped_repo_points([90.0, 10.0], 0.4) == [40.0, 10.0]
        assert capped_repo_points([50.0, 50.0], 0.4) == [40.0, 40.0]
        assert capped_repo_points([], 0.4) == []
        assert capped_repo_points([0.0, 0.0], 0.4) == [0.0, 0.0]


class TestPushVolumeCap:
    def test_bulk_pushing_beyond_cap_adds_nothing(self, cfg: ScoringConfig) -> None:
        cap = cfg.contributor_expert.caps.push_events_counted_max
        zero = dict.fromkeys(
            [
                "pull_requests_opened",
                "merged_pull_requests_authored",
                "reviews_submitted",
                "issues_opened",
                "issue_comments",
            ],
            0,
        )
        rows = [
            contributor_row("bulk", REPOS[0], push_events=cap * 1000, **zero),
            contributor_row("atcap", REPOS[1], push_events=cap, **zero),
        ]
        frame = _score(cfg, rows)
        points = dict(
            zip(
                frame.get_column("actor_login").to_list(),
                frame.get_column("weighted_event_points").to_list(),
                strict=True,
            )
        )
        assert points["bulk"] == pytest.approx(points["atcap"])
        # Raw counts remain uncapped (raw AND weighted kept, spec 16.2).
        raw = dict(
            zip(
                frame.get_column("actor_login").to_list(),
                frame.get_column("raw_event_count").to_list(),
                strict=True,
            )
        )
        assert raw["bulk"] == cap * 1000
        assert raw["atcap"] == cap


class TestMeaningfulActiveDays:
    def test_single_day_contributor_excluded(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row(
                "oneday",
                REPOS[0],
                active_days=1,
                active_months=1,
                first_seen=date(2026, 6, 1),
                last_seen=date(2026, 6, 1),
            ),
            contributor_row("regular", REPOS[1]),
        ]
        frame = _score(cfg, rows)
        assert frame.get_column("actor_login").to_list() == ["regular"]

    def test_two_days_in_one_repo_included(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row(
                "twodays",
                REPOS[0],
                active_days=2,
                active_months=1,
                first_seen=date(2026, 6, 1),
                last_seen=date(2026, 6, 2),
            )
        ]
        assert _score(cfg, rows).get_column("actor_login").to_list() == ["twodays"]

    def test_one_day_each_in_two_repos_on_distinct_dates_included(self, cfg: ScoringConfig) -> None:
        # Per-repo active_days are both 1, but the distinct first/last dates
        # prove at least two meaningful active days across the domain.
        rows = [
            contributor_row(
                "split",
                REPOS[0],
                active_days=1,
                active_months=1,
                first_seen=date(2026, 5, 10),
                last_seen=date(2026, 5, 10),
            ),
            contributor_row(
                "split",
                REPOS[1],
                active_days=1,
                active_months=1,
                first_seen=date(2026, 6, 20),
                last_seen=date(2026, 6, 20),
            ),
        ]
        assert _score(cfg, rows).get_column("actor_login").to_list() == ["split"]

    def test_one_day_each_in_two_repos_same_date_excluded(self, cfg: ScoringConfig) -> None:
        same = {
            "active_days": 1,
            "active_months": 1,
            "first_seen": date(2026, 6, 1),
            "last_seen": date(2026, 6, 1),
        }
        rows = [
            contributor_row("sameday", REPOS[0], **same),
            contributor_row("sameday", REPOS[1], **same),
        ]
        assert _score(cfg, rows).height == 0


class TestOneRepoMarking:
    def test_one_repo_contributor_marked(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row("solo", REPOS[0]),
            contributor_row("multi", REPOS[0]),
            contributor_row("multi", REPOS[1]),
        ]
        frame = _score(cfg, rows)
        by_actor = {row["actor_login"]: row for row in frame.to_dicts()}
        assert by_actor["solo"]["one_repo"] is True
        assert by_actor["solo"]["qualified_repo_count"] == 1
        assert by_actor["multi"]["one_repo"] is False
        assert by_actor["multi"]["qualified_repo_count"] == 2


class TestOutputContract:
    def test_columns_and_sorting(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row("zeta", REPOS[0]),
            contributor_row("alpha", REPOS[1]),
        ]
        frame = _score(cfg, rows)
        assert frame.columns == list(CONTRIBUTOR_SCORE_COLUMNS)
        assert frame.get_column("actor_login").to_list() == ["alpha", "zeta"]

    def test_scores_bounded_and_weighted_sum_matches(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row("alice", REPOS[0], merged_pull_requests_authored=30),
            contributor_row("alice", REPOS[2]),
            contributor_row("bob", REPOS[1], reviews_submitted=0, merged_pull_requests_authored=0),
            contributor_row("carol", REPOS[2], push_events=500),
        ]
        frame = _score(cfg, rows)
        weights = dict(cfg.contributor_expert.weights)
        for row in frame.to_dicts():
            for column in (
                "expert_score",
                "domain_activity_score",
                "contribution_quality_score",
                "repository_quality_exposure_score",
                "continuity_score",
                "collaboration_score",
            ):
                assert 0.0 <= row[column] <= 100.0, column
            expected = (
                weights["domain_activity"] * row["domain_activity_score"]
                + weights["contribution_quality"] * row["contribution_quality_score"]
                + weights["repository_quality_exposure"] * row["repository_quality_exposure_score"]
                + weights["continuity"] * row["continuity_score"]
                + weights["collaboration"] * row["collaboration_score"]
            )
            assert row["expert_score"] == pytest.approx(expected, abs=1e-9)

    def test_location_join_and_unlocated_nulls(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row("located", REPOS[0]),
            contributor_row("unlocated", REPOS[1]),
        ]
        locations = pl.DataFrame([location_row("located")])
        frame = _score(cfg, rows, locations)
        by_actor = {row["actor_login"]: row for row in frame.to_dicts()}
        assert by_actor["located"]["country_code"] == "US"
        assert by_actor["located"]["city"] == "Seattle"
        assert by_actor["located"]["location_confidence"] == "high"
        assert by_actor["unlocated"]["country_code"] is None
        assert by_actor["unlocated"]["city"] is None
        assert by_actor["unlocated"]["location_confidence"] == "unusable"

    def test_only_qualified_repositories_count(self, cfg: ScoringConfig) -> None:
        # Activity in a rejected repository contributes nothing.
        classification = pl.DataFrame(
            [
                classification_row(REPOS[0]),
                classification_row(REPOS[1], classification_status="rejected"),
            ]
        )
        activity = pl.DataFrame(
            [
                contributor_row("alice", REPOS[0]),
                contributor_row("alice", REPOS[1], merged_pull_requests_authored=500),
            ]
        )
        frame = score_contributors(
            activity,
            classification,
            repo_scores_frame({REPOS[0]: 80.0}),
            _locations(["alice"]),
            cfg,
            WINDOW_END,
        )
        row = frame.to_dicts()[0]
        assert row["qualified_repo_count"] == 1
        assert row["one_repo"] is True

    def test_exposure_reflects_repo_quality(self, cfg: ScoringConfig) -> None:
        rows = [
            contributor_row("highrepo", REPOS[0]),  # quality 90
            contributor_row("lowrepo", REPOS[2]),  # quality 20
        ]
        frame = _score(cfg, rows)
        by_actor = {
            row["actor_login"]: row["repository_quality_exposure_score"] for row in frame.to_dicts()
        }
        assert by_actor["highrepo"] == pytest.approx(90.0)
        assert by_actor["lowrepo"] == pytest.approx(20.0)

    def test_empty_activity_gives_empty_frame(self, cfg: ScoringConfig) -> None:
        activity = pl.DataFrame([contributor_row("a", REPOS[0])]).filter(pl.lit(False))
        frame = score_contributors(
            activity, _classification(), _repo_scores(), _locations([]), cfg, WINDOW_END
        )
        assert frame.height == 0
        assert frame.columns == list(CONTRIBUTOR_SCORE_COLUMNS)

    def test_deterministic_and_byte_identical(self, cfg: ScoringConfig, tmp_path: Path) -> None:
        rows = [
            contributor_row("alice", REPOS[0], merged_pull_requests_authored=30),
            contributor_row("alice", REPOS[2]),
            contributor_row("bob", REPOS[1]),
            contributor_row("carol", REPOS[2], push_events=500),
        ]
        first = _score(cfg, rows)
        second = _score(cfg, rows)
        assert first.equals(second)
        path_a = tmp_path / "a.parquet"
        path_b = tmp_path / "b.parquet"
        first.write_parquet(path_a)
        second.write_parquet(path_b)
        assert path_a.read_bytes() == path_b.read_bytes()
