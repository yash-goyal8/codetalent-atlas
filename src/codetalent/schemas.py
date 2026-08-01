"""Core data schemas (spec section 9).

Pydantic models for every pipeline table, field-for-field with the build
specification. Matching Parquet schemas are derived from these models in the
milestones that materialize each table.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Count = Annotated[int, Field(ge=0)]
Score = Annotated[float, Field(ge=0.0, le=100.0)]
Share = Annotated[float, Field(ge=0.0, le=1.0)]


class ClassificationStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    BORDERLINE = "borderline"


class AccountType(StrEnum):
    USER = "user"
    BOT = "bot"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class FetchStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class LocationLevel(StrEnum):
    CITY = "city"
    COUNTRY = "country"
    REGION = "region"
    UNKNOWN = "unknown"


class LocationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNUSABLE = "unusable"


class NormalizationMethod(StrEnum):
    EXACT_ALIAS = "exact_alias"
    PARSED_COUNTRY = "parsed_country"
    UNIQUE_CITY = "unique_city"
    CITY_COUNTRY_PAIR = "city_country_pair"
    MANUAL_OVERRIDE = "manual_override"
    UNRESOLVED = "unresolved"


class GeoLevel(StrEnum):
    COUNTRY = "country"
    CITY = "city"


class RecommendationTier(StrEnum):
    PRIORITY = "priority"
    PROMISING = "promising"
    MONITOR = "monitor"
    INSUFFICIENT_DATA = "insufficient_data"


class AtlasModel(BaseModel):
    """Base model: strict field set, immutable records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RepositoryActivitySummary(AtlasModel):
    """Spec 9.1: per-repository event aggregates from GH Archive discovery."""

    repo_name: str
    owner_login: str
    repo_short_name: str
    unique_human_contributors: Count
    active_days: Count
    active_months: Count
    push_events: Count
    push_commit_count: Count
    pull_requests_opened: Count
    pull_requests_closed: Count
    merged_pull_requests: Count
    reviews_submitted: Count
    issues_opened: Count
    issue_comments: Count
    releases: Count
    weighted_activity_score: Annotated[float, Field(ge=0.0)]
    first_seen: date
    last_seen: date
    automation_event_share: Share
    single_actor_event_share: Share
    discovery_status: str
    exclusion_reason: str | None = None


class RepositoryMetadata(AtlasModel):
    """Spec 9.2: GraphQL-enriched repository metadata."""

    repo_name: str
    description: str | None = None
    is_fork: bool
    is_archived: bool
    is_disabled: bool
    primary_language: str | None = None
    topics: list[str]
    stargazer_count: Count
    fork_count: Count
    license_spdx_id: str | None = None
    pushed_at: datetime | None = None
    updated_at: datetime | None = None
    release_count: Count
    issue_count: Count
    pull_request_count: Count
    has_readme: bool | None = None
    has_contributing: bool | None = None
    has_code_of_conduct: bool | None = None
    has_ci: bool | None = None
    has_tests_signal: bool | None = None
    graphql_fetched_at: datetime


class RepositoryClassification(AtlasModel):
    """Spec 9.3: deterministic taxonomy classification with evidence."""

    repo_name: str
    domain_id: str
    subdomains: list[str]
    classification_score: Score
    classification_status: ClassificationStatus
    evidence_topics: list[str]
    evidence_terms: list[str]
    evidence_files: list[str]
    negative_evidence: list[str]
    manual_label: str | None = None
    manual_notes: str | None = None


class ContributorActivity(AtlasModel):
    """Spec 9.4: per-contributor, per-repository domain activity."""

    actor_login: str
    repo_name: str
    domain_id: str
    subdomains: list[str]
    push_events: Count
    pull_requests_opened: Count
    merged_pull_requests_authored: Count
    reviews_submitted: Count
    issues_opened: Count
    issue_comments: Count
    active_days: Count
    active_months: Count
    first_seen: date
    last_seen: date
    raw_contribution_points: Annotated[float, Field(ge=0.0)]


class UserProfile(AtlasModel):
    """Spec 9.5: public user profile enrichment (no emails, names, or employers)."""

    actor_login: str
    account_type: AccountType
    public_location_raw: str | None = None
    created_at: datetime | None = None
    followers_count: Count | None = None
    profile_fetched_at: datetime
    fetch_status: FetchStatus


class NormalizedLocation(AtlasModel):
    """Spec 9.6: offline location normalization output (local-only, never published)."""

    actor_login: str
    raw_location: str | None = None
    normalized_country_code: str | None = None
    normalized_country_name: str | None = None
    normalized_city: str | None = None
    latitude: Annotated[float, Field(ge=-90.0, le=90.0)] | None = None
    longitude: Annotated[float, Field(ge=-180.0, le=180.0)] | None = None
    location_level: LocationLevel
    location_confidence: LocationConfidence
    normalization_method: NormalizationMethod
    ambiguity_reason: str | None = None


class ContributorScore(AtlasModel):
    """Spec 9.7: domain-specific contributor expert score (local-only, never published)."""

    actor_login: str
    domain_id: str
    expert_score: Score
    domain_activity_score: Score
    contribution_quality_score: Score
    repository_quality_exposure_score: Score
    continuity_score: Score
    collaboration_score: Score
    qualified_repo_count: Count
    active_months: Count
    country_code: str | None = None
    city: str | None = None
    location_confidence: str


class GeographicRanking(AtlasModel):
    """Spec 9.8: aggregate country/city opportunity and confidence ranking."""

    geo_level: GeoLevel
    geo_id: str
    country_code: str
    city: str | None = None
    domain_id: str
    opportunity_score: Score
    confidence_score: Score
    expert_supply_score: Score
    expert_quality_score: Score
    collaboration_depth_score: Score
    momentum_score: Score
    ecosystem_breadth_score: Score
    observable_expert_count: Count
    weighted_expert_count: Annotated[float, Field(ge=0.0)]
    qualified_repo_count: Count
    organization_count: Count
    multi_repo_expert_share: Share
    located_profile_coverage: Share
    high_confidence_location_share: Share
    top_subdomains: list[str]
    rank: Count
    recommendation_tier: RecommendationTier
