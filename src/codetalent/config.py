"""Typed loaders for the configuration contracts in ``config/`` (spec section 8).

Every loader validates structure with Pydantic and fails loudly on invalid or
missing configuration, per the spec failure policy ("invalid configuration:
fail immediately"). No scoring weight may exist only in source code, so
``scoring.yaml`` is the single source of truth for all weights and thresholds.
"""

from __future__ import annotations

import csv
import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from codetalent.schemas import LocationLevel

DEFAULT_CONFIG_DIR = Path("config")

Weight = Annotated[float, Field(ge=0.0, le=1.0)]
Share = Annotated[float, Field(ge=0.0, le=1.0)]

_WEIGHT_SUM_TOLERANCE = 1e-9


class ConfigError(Exception):
    """Raised when a configuration file is missing, unparseable, or invalid."""


class StrictModel(BaseModel):
    """Base for config models: unknown keys are configuration errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_weights_sum_to_one(weights: dict[str, float], context: str) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"{context} weights must sum to 1.0, got {total}")


# --- domains.yaml -----------------------------------------------------------


class DomainStatus(StrEnum):
    PILOT = "pilot"
    PLANNED = "planned"


class DomainEntry(StrictModel):
    display_name: str
    status: DomainStatus
    taxonomy_file: str | None = None

    @model_validator(mode="after")
    def _pilot_requires_taxonomy(self) -> DomainEntry:
        if self.status is DomainStatus.PILOT and not self.taxonomy_file:
            raise ValueError("pilot domains must reference a taxonomy_file")
        return self


class DomainsConfig(StrictModel):
    domains: dict[str, DomainEntry]

    @model_validator(mode="after")
    def _exactly_one_pilot(self) -> DomainsConfig:
        pilots = [k for k, v in self.domains.items() if v.status is DomainStatus.PILOT]
        if len(pilots) != 1:
            raise ValueError(f"exactly one pilot domain is required, got {pilots}")
        return self


# --- cloud_devops_taxonomy.yaml ---------------------------------------------


class SubdomainTaxonomy(StrictModel):
    display_name: str
    positive_topics: Annotated[list[str], Field(min_length=1)]
    positive_terms: Annotated[list[str], Field(min_length=1)]
    positive_files: list[str] = []
    negative_terms: list[str] = []


class TaxonomyConfig(StrictModel):
    domain_id: str
    display_name: str
    subdomains: dict[str, SubdomainTaxonomy]

    @model_validator(mode="after")
    def _has_subdomains(self) -> TaxonomyConfig:
        if not self.subdomains:
            raise ValueError("taxonomy must define at least one subdomain")
        return self


# --- repo_filters.yaml ------------------------------------------------------


class ActivityWindow(StrictModel):
    pilot_start: str
    pilot_end: str
    expanded_months: Annotated[int, Field(ge=1)]


class FilterMinimums(StrictModel):
    unique_human_contributors: Annotated[int, Field(ge=0)]
    meaningful_events: Annotated[int, Field(ge=0)]
    pull_requests_or_reviews: Annotated[int, Field(ge=0)]
    active_months: Annotated[int, Field(ge=0)]


class FilterRequirements(StrictModel):
    must_be_public: bool
    must_not_be_fork: bool
    must_not_be_archived: bool
    must_not_be_disabled: bool
    require_recognized_license: bool
    require_recent_activity: bool


class FilterExclusions(StrictModel):
    tutorial_only: bool
    dotfiles: bool
    student_assignments: bool
    interview_prep: bool
    awesome_lists: bool
    documentation_only: bool
    mirrors: bool
    generated_copies: bool
    single_contributor_dominance_threshold: Share


class RepoFiltersConfig(StrictModel):
    activity_window: ActivityWindow
    minimums: FilterMinimums
    requirements: FilterRequirements
    exclusions: FilterExclusions


# --- scoring.yaml -----------------------------------------------------------


class EventWeights(StrictModel):
    merged_pull_request: Annotated[float, Field(gt=0)]
    pull_request_review: Annotated[float, Field(gt=0)]
    pull_request_opened: Annotated[float, Field(gt=0)]
    release: Annotated[float, Field(gt=0)]
    push_event: Annotated[float, Field(gt=0)]
    issue_opened: Annotated[float, Field(gt=0)]
    issue_comment: Annotated[float, Field(gt=0)]


class RepositoryQualityWeights(StrictModel):
    recent_activity: Weight
    contributor_diversity: Weight
    collaboration_quality: Weight
    technical_relevance: Weight
    repository_maturity: Weight

    @model_validator(mode="after")
    def _sums_to_one(self) -> RepositoryQualityWeights:
        _check_weights_sum_to_one(dict(self), "repository_quality")
        return self


class RepositoryQualityConfig(StrictModel):
    weights: RepositoryQualityWeights
    winsorization_percentile: Annotated[float, Field(gt=0.0, lt=1.0)]


class ContributorExpertWeights(StrictModel):
    domain_activity: Weight
    contribution_quality: Weight
    repository_quality_exposure: Weight
    continuity: Weight
    collaboration: Weight

    @model_validator(mode="after")
    def _sums_to_one(self) -> ContributorExpertWeights:
        _check_weights_sum_to_one(dict(self), "contributor_expert")
        return self


class ContributorCaps(StrictModel):
    single_repository_share: Share


class ContributorMinimums(StrictModel):
    meaningful_active_days: Annotated[int, Field(ge=0)]


class ContributorExpertConfig(StrictModel):
    weights: ContributorExpertWeights
    caps: ContributorCaps
    minimums: ContributorMinimums


class OpportunityWeights(StrictModel):
    expert_supply: Weight
    expert_quality: Weight
    collaboration_depth: Weight
    momentum: Weight
    ecosystem_breadth: Weight

    @model_validator(mode="after")
    def _sums_to_one(self) -> OpportunityWeights:
        _check_weights_sum_to_one(dict(self), "opportunity")
        return self


class ConfidenceWeights(StrictModel):
    located_profile_coverage: Weight
    location_certainty: Weight
    sample_size_adequacy: Weight
    repository_diversity: Weight
    organization_diversity: Weight

    @model_validator(mode="after")
    def _sums_to_one(self) -> ConfidenceWeights:
        _check_weights_sum_to_one(dict(self), "confidence")
        return self


class OpportunityConfig(StrictModel):
    weights: OpportunityWeights


class ConfidenceConfig(StrictModel):
    weights: ConfidenceWeights


class CountryMinimumSamples(StrictModel):
    located_contributors: Annotated[int, Field(ge=1)]
    qualified_repositories: Annotated[int, Field(ge=1)]
    organizations: Annotated[int, Field(ge=1)]


class CityMinimumSamples(StrictModel):
    high_confidence_located_contributors: Annotated[int, Field(ge=1)]
    qualified_repositories: Annotated[int, Field(ge=1)]
    organizations: Annotated[int, Field(ge=1)]


class MinimumSamples(StrictModel):
    country: CountryMinimumSamples
    city: CityMinimumSamples


class ThresholdTier(StrictModel):
    min_opportunity: Annotated[float, Field(ge=0, le=100)]
    min_confidence: Annotated[float, Field(ge=0, le=100)]


class MonitorTier(StrictModel):
    """Monitor rule: opportunity >= min_opportunity OR confidence within the band."""

    min_opportunity: Annotated[float, Field(ge=0, le=100)]
    confidence_band_min: Annotated[float, Field(ge=0, le=100)]
    confidence_band_max: Annotated[float, Field(ge=0, le=100)]

    @model_validator(mode="after")
    def _band_is_ordered(self) -> MonitorTier:
        if self.confidence_band_min > self.confidence_band_max:
            raise ValueError("monitor confidence band is inverted")
        return self


class InsufficientDataTier(StrictModel):
    """Fallback tier: minimum-sample rule failed or confidence below this bound."""

    max_confidence: Annotated[float, Field(ge=0, le=100)]


class RecommendationTiers(StrictModel):
    priority: ThresholdTier
    promising: ThresholdTier
    monitor: MonitorTier
    insufficient_data: InsufficientDataTier


class ConcentrationConfig(StrictModel):
    organization_share_flag: Share
    single_actor_event_share_max: Share


class ScoringConfig(StrictModel):
    event_weights: EventWeights
    repository_quality: RepositoryQualityConfig
    contributor_expert: ContributorExpertConfig
    opportunity: OpportunityConfig
    confidence: ConfidenceConfig
    minimum_samples: MinimumSamples
    tiers: RecommendationTiers
    concentration: ConcentrationConfig


# --- bot_patterns.yaml ------------------------------------------------------


class BotPatternsConfig(StrictModel):
    login_suffixes: Annotated[list[str], Field(min_length=1)]
    exact_logins: Annotated[list[str], Field(min_length=1)]
    substring_patterns: list[str] = []
    regex_patterns: list[str] = []

    @field_validator("regex_patterns")
    @classmethod
    def _regexes_compile(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid bot regex {pattern!r}: {exc}") from exc
        return patterns


# --- location CSVs ----------------------------------------------------------

_ALIAS_HEADER = ["alias", "normalized_country_code", "normalized_city", "location_level", "notes"]
_OVERRIDE_HEADER = [
    "raw_location",
    "normalized_country_code",
    "normalized_city",
    "location_level",
    "evidence_note",
]

CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class LocationAlias(StrictModel):
    alias: Annotated[str, Field(min_length=1)]
    normalized_country_code: CountryCode
    normalized_city: str | None = None
    location_level: Literal[LocationLevel.CITY, LocationLevel.COUNTRY, LocationLevel.REGION]
    notes: str | None = None

    @model_validator(mode="after")
    def _city_level_requires_city(self) -> LocationAlias:
        if self.location_level is LocationLevel.CITY and not self.normalized_city:
            raise ValueError(f"alias {self.alias!r}: city-level alias needs normalized_city")
        return self


class LocationOverride(StrictModel):
    raw_location: Annotated[str, Field(min_length=1)]
    normalized_country_code: CountryCode
    normalized_city: str | None = None
    location_level: Literal[LocationLevel.CITY, LocationLevel.COUNTRY, LocationLevel.REGION]
    evidence_note: Annotated[str, Field(min_length=1)]  # spec: every override needs a note


# --- loaders ----------------------------------------------------------------


def _load_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ConfigError(f"missing configuration file: {path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"unparseable YAML in {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at the top level")
    return loaded


def _validate[T: BaseModel](model: type[T], data: object, path: Path) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration in {path}:\n{exc}") from exc


def load_domains(path: Path) -> DomainsConfig:
    return _validate(DomainsConfig, _load_yaml_mapping(path), path)


def load_taxonomy(path: Path) -> TaxonomyConfig:
    return _validate(TaxonomyConfig, _load_yaml_mapping(path), path)


def load_repo_filters(path: Path) -> RepoFiltersConfig:
    return _validate(RepoFiltersConfig, _load_yaml_mapping(path), path)


def load_scoring(path: Path) -> ScoringConfig:
    return _validate(ScoringConfig, _load_yaml_mapping(path), path)


def load_bot_patterns(path: Path) -> BotPatternsConfig:
    return _validate(BotPatternsConfig, _load_yaml_mapping(path), path)


def _read_csv_rows(path: Path, expected_header: list[str]) -> list[dict[str, str | None]]:
    if not path.is_file():
        raise ConfigError(f"missing configuration file: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_header:
            raise ConfigError(
                f"{path} header must be {','.join(expected_header)!r}, got {reader.fieldnames!r}"
            )
        return [{k: (v if v != "" else None) for k, v in row.items()} for row in reader]


def load_location_aliases(path: Path) -> list[LocationAlias]:
    return [_validate(LocationAlias, row, path) for row in _read_csv_rows(path, _ALIAS_HEADER)]


def load_location_overrides(path: Path) -> list[LocationOverride]:
    return [
        _validate(LocationOverride, row, path) for row in _read_csv_rows(path, _OVERRIDE_HEADER)
    ]


class AtlasConfig(StrictModel):
    """All configuration contracts, loaded and cross-validated."""

    domains: DomainsConfig
    taxonomies: dict[str, TaxonomyConfig]
    repo_filters: RepoFiltersConfig
    scoring: ScoringConfig
    bot_patterns: BotPatternsConfig
    location_aliases: list[LocationAlias]
    location_overrides: list[LocationOverride]


def load_all(config_dir: Path = DEFAULT_CONFIG_DIR) -> AtlasConfig:
    """Load and validate every configuration contract; raise ``ConfigError`` on any problem."""
    domains = load_domains(config_dir / "domains.yaml")

    taxonomies: dict[str, TaxonomyConfig] = {}
    for domain_id, entry in domains.domains.items():
        if entry.taxonomy_file is None:
            continue
        taxonomy_path = config_dir / entry.taxonomy_file
        taxonomy = load_taxonomy(taxonomy_path)
        if taxonomy.domain_id != domain_id:
            raise ConfigError(
                f"{taxonomy_path}: domain_id {taxonomy.domain_id!r} does not match "
                f"domains.yaml key {domain_id!r}"
            )
        taxonomies[domain_id] = taxonomy

    return AtlasConfig(
        domains=domains,
        taxonomies=taxonomies,
        repo_filters=load_repo_filters(config_dir / "repo_filters.yaml"),
        scoring=load_scoring(config_dir / "scoring.yaml"),
        bot_patterns=load_bot_patterns(config_dir / "bot_patterns.yaml"),
        location_aliases=load_location_aliases(config_dir / "location_aliases.csv"),
        location_overrides=load_location_overrides(config_dir / "location_overrides.csv"),
    )
