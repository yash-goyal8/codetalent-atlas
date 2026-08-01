"""Schema tests: bounds, enum round-trips, and rejection of out-of-range values."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from codetalent import schemas

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def activity_summary_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "repo_name": "acme/terraform-widgets",
        "owner_login": "acme",
        "repo_short_name": "terraform-widgets",
        "unique_human_contributors": 12,
        "active_days": 40,
        "active_months": 3,
        "push_events": 200,
        "push_commit_count": 340,
        "pull_requests_opened": 55,
        "pull_requests_closed": 50,
        "merged_pull_requests": 45,
        "reviews_submitted": 80,
        "issues_opened": 30,
        "issue_comments": 120,
        "releases": 4,
        "weighted_activity_score": 1234.5,
        "first_seen": date(2026, 5, 2),
        "last_seen": date(2026, 7, 30),
        "automation_event_share": 0.12,
        "single_actor_event_share": 0.35,
        "discovery_status": "candidate",
        "exclusion_reason": None,
    }
    payload.update(overrides)
    return payload


def geographic_ranking_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "geo_level": "country",
        "geo_id": "DE",
        "country_code": "DE",
        "city": None,
        "domain_id": "cloud_devops",
        "opportunity_score": 71.2,
        "confidence_score": 66.0,
        "expert_supply_score": 70.0,
        "expert_quality_score": 68.0,
        "collaboration_depth_score": 75.0,
        "momentum_score": 60.0,
        "ecosystem_breadth_score": 65.0,
        "observable_expert_count": 480,
        "weighted_expert_count": 350.5,
        "qualified_repo_count": 140,
        "organization_count": 42,
        "multi_repo_expert_share": 0.4,
        "located_profile_coverage": 0.52,
        "high_confidence_location_share": 0.31,
        "top_subdomains": ["infrastructure_as_code"],
        "rank": 4,
        "recommendation_tier": "promising",
    }
    payload.update(overrides)
    return payload


def contributor_score_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "actor_login": "octocat",
        "domain_id": "cloud_devops",
        "expert_score": 88.0,
        "domain_activity_score": 90.0,
        "contribution_quality_score": 85.0,
        "repository_quality_exposure_score": 80.0,
        "continuity_score": 92.0,
        "collaboration_score": 87.0,
        "qualified_repo_count": 6,
        "active_months": 3,
        "country_code": "DE",
        "city": "Berlin",
        "location_confidence": "high",
    }
    payload.update(overrides)
    return payload


class TestEnumRoundTrips:
    @pytest.mark.parametrize(
        ("enum_cls", "values"),
        [
            (schemas.ClassificationStatus, ["accepted", "rejected", "borderline"]),
            (schemas.AccountType, ["user", "bot", "organization", "unknown"]),
            (schemas.FetchStatus, ["success", "not_found", "rate_limited", "error"]),
            (schemas.LocationLevel, ["city", "country", "region", "unknown"]),
            (schemas.LocationConfidence, ["high", "medium", "low", "unusable"]),
            (
                schemas.NormalizationMethod,
                [
                    "exact_alias",
                    "parsed_country",
                    "unique_city",
                    "city_country_pair",
                    "manual_override",
                    "unresolved",
                ],
            ),
            (schemas.GeoLevel, ["country", "city"]),
            (
                schemas.RecommendationTier,
                ["priority", "promising", "monitor", "insufficient_data"],
            ),
        ],
    )
    def test_values_round_trip(self, enum_cls: type[schemas.StrEnum], values: list[str]) -> None:
        assert sorted(m.value for m in enum_cls) == sorted(values)
        for value in values:
            assert enum_cls(value).value == value

    def test_invalid_enum_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            schemas.GeographicRanking(**geographic_ranking_payload(recommendation_tier="maybe"))


class TestRepositoryActivitySummary:
    def test_valid_payload_accepted(self) -> None:
        summary = schemas.RepositoryActivitySummary(**activity_summary_payload())
        assert summary.repo_name == "acme/terraform-widgets"
        assert summary.exclusion_reason is None

    @pytest.mark.parametrize(
        "overrides",
        [
            {"unique_human_contributors": -1},
            {"push_events": -5},
            {"weighted_activity_score": -0.1},
            {"automation_event_share": 1.2},
            {"single_actor_event_share": -0.01},
        ],
    )
    def test_out_of_range_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            schemas.RepositoryActivitySummary(**activity_summary_payload(**overrides))

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            schemas.RepositoryActivitySummary(**activity_summary_payload(surprise=1))


class TestRepositoryMetadata:
    def test_valid_payload_accepted(self) -> None:
        metadata = schemas.RepositoryMetadata(
            repo_name="acme/terraform-widgets",
            description="Terraform modules for widgets",
            is_fork=False,
            is_archived=False,
            is_disabled=False,
            primary_language="HCL",
            topics=["terraform", "iac"],
            stargazer_count=420,
            fork_count=37,
            license_spdx_id="Apache-2.0",
            pushed_at=NOW,
            updated_at=NOW,
            release_count=9,
            issue_count=55,
            pull_request_count=140,
            has_readme=True,
            has_contributing=None,
            has_code_of_conduct=None,
            has_ci=True,
            has_tests_signal=True,
            graphql_fetched_at=NOW,
        )
        assert metadata.topics == ["terraform", "iac"]

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValidationError):
            schemas.RepositoryMetadata(
                repo_name="acme/x",
                is_fork=False,
                is_archived=False,
                is_disabled=False,
                topics=[],
                stargazer_count=-1,
                fork_count=0,
                release_count=0,
                issue_count=0,
                pull_request_count=0,
                graphql_fetched_at=NOW,
            )


class TestClassificationAndActivity:
    def test_classification_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            schemas.RepositoryClassification(
                repo_name="acme/x",
                domain_id="cloud_devops",
                subdomains=["infrastructure_as_code"],
                classification_score=100.5,
                classification_status=schemas.ClassificationStatus.ACCEPTED,
                evidence_topics=["terraform"],
                evidence_terms=[],
                evidence_files=[],
                negative_evidence=[],
            )

    def test_contributor_activity_valid(self) -> None:
        activity = schemas.ContributorActivity(
            actor_login="octocat",
            repo_name="acme/terraform-widgets",
            domain_id="cloud_devops",
            subdomains=["infrastructure_as_code"],
            push_events=30,
            pull_requests_opened=12,
            merged_pull_requests_authored=10,
            reviews_submitted=18,
            issues_opened=3,
            issue_comments=25,
            active_days=22,
            active_months=3,
            first_seen=date(2026, 5, 3),
            last_seen=date(2026, 7, 29),
            raw_contribution_points=182.0,
        )
        assert activity.raw_contribution_points == pytest.approx(182.0)


class TestUserProfileAndLocation:
    def test_profile_valid(self) -> None:
        profile = schemas.UserProfile(
            actor_login="octocat",
            account_type=schemas.AccountType.USER,
            public_location_raw="Berlin, Germany",
            created_at=NOW,
            followers_count=None,
            profile_fetched_at=NOW,
            fetch_status=schemas.FetchStatus.SUCCESS,
        )
        assert profile.account_type is schemas.AccountType.USER

    @pytest.mark.parametrize(
        ("latitude", "longitude"), [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -180.5)]
    )
    def test_coordinates_bounded(self, latitude: float, longitude: float) -> None:
        with pytest.raises(ValidationError):
            schemas.NormalizedLocation(
                actor_login="octocat",
                raw_location="Berlin",
                normalized_country_code="DE",
                normalized_country_name="Germany",
                normalized_city="Berlin",
                latitude=latitude,
                longitude=longitude,
                location_level=schemas.LocationLevel.CITY,
                location_confidence=schemas.LocationConfidence.HIGH,
                normalization_method=schemas.NormalizationMethod.UNIQUE_CITY,
            )


class TestScores:
    @pytest.mark.parametrize(
        "field",
        [
            "expert_score",
            "domain_activity_score",
            "contribution_quality_score",
            "repository_quality_exposure_score",
            "continuity_score",
            "collaboration_score",
        ],
    )
    @pytest.mark.parametrize("bad_value", [-0.1, 100.1])
    def test_contributor_scores_bounded_0_100(self, field: str, bad_value: float) -> None:
        with pytest.raises(ValidationError):
            schemas.ContributorScore(**contributor_score_payload(**{field: bad_value}))

    def test_geographic_ranking_valid(self) -> None:
        ranking = schemas.GeographicRanking(**geographic_ranking_payload())
        assert ranking.recommendation_tier is schemas.RecommendationTier.PROMISING

    @pytest.mark.parametrize(
        "overrides",
        [
            {"opportunity_score": 101.0},
            {"confidence_score": -1.0},
            {"multi_repo_expert_share": 1.01},
            {"located_profile_coverage": -0.2},
            {"observable_expert_count": -3},
            {"rank": -1},
        ],
    )
    def test_geographic_out_of_range_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            schemas.GeographicRanking(**geographic_ranking_payload(**overrides))
