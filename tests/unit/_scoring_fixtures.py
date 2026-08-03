"""Synthetic-fixture builders for the scoring engine tests (no real data reads)."""

from __future__ import annotations

import copy
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from codetalent.config import ScoringConfig

WINDOW_END = date(2026, 7, 31)


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def scoring_config(config_dir: Path, overrides: dict[str, Any] | None = None) -> ScoringConfig:
    """Load the real scoring.yaml, optionally deep-merging overrides."""
    raw = yaml.safe_load((config_dir / "scoring.yaml").read_text(encoding="utf-8"))
    if overrides:
        raw = deep_merge(raw, overrides)
    return ScoringConfig.model_validate(raw)


#: Lowered minimum-sample rules so small synthetic geographies can pass gates.
SMALL_SAMPLE_OVERRIDES: dict[str, Any] = {
    "minimum_samples": {
        "country": {"located_contributors": 3, "qualified_repositories": 2, "organizations": 2},
        "city": {
            "high_confidence_located_contributors": 3,
            "qualified_repositories": 2,
            "organizations": 2,
        },
    }
}


def activity_row(repo_name: str, **overrides: object) -> dict[str, object]:
    """One spec 9.1 repository activity summary row."""
    owner, short = repo_name.split("/", 1)
    row: dict[str, object] = {
        "repo_name": repo_name,
        "owner_login": owner,
        "repo_short_name": short,
        "unique_human_contributors": 8,
        "active_days": 30,
        "active_months": 3,
        "push_events": 40,
        "push_commit_count": 0,
        "pull_requests_opened": 20,
        "pull_requests_closed": 18,
        "merged_pull_requests": 15,
        "reviews_submitted": 25,
        "issues_opened": 10,
        "issue_comments": 30,
        "releases": 2,
        "weighted_activity_score": 500.0,
        "first_seen": date(2026, 5, 2),
        "last_seen": date(2026, 7, 30),
        "automation_event_share": 0.1,
        "single_actor_event_share": 0.3,
        "discovery_status": "activity_passed",
        "exclusion_reason": None,
    }
    row.update(overrides)
    return row


def metadata_row(repo_name: str, **overrides: object) -> dict[str, object]:
    """One spec 9.2 repository metadata row."""
    row: dict[str, object] = {
        "repo_name": repo_name,
        "description": "terraform tooling",
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "primary_language": "Go",
        "topics": ["terraform"],
        "stargazer_count": 100,
        "fork_count": 10,
        "license_spdx_id": "Apache-2.0",
        "pushed_at": datetime(2026, 7, 30),
        "updated_at": datetime(2026, 7, 30),
        "release_count": 3,
        "issue_count": 20,
        "pull_request_count": 40,
        "has_readme": True,
        "has_contributing": True,
        "has_code_of_conduct": None,
        "has_ci": True,
        "has_tests_signal": None,
        "graphql_fetched_at": datetime(2026, 8, 1),
    }
    row.update(overrides)
    return row


def classification_row(repo_name: str, **overrides: object) -> dict[str, object]:
    """One spec 9.3 repository classification row (accepted by default)."""
    row: dict[str, object] = {
        "repo_name": repo_name,
        "domain_id": "cloud_devops",
        "subdomains": ["infrastructure_as_code"],
        "classification_score": 6.0,
        "classification_status": "accepted",
        "evidence_topics": ["terraform"],
        "evidence_terms": ["terraform"],
        "evidence_files": [],
        "negative_evidence": [],
        "manual_label": None,
        "manual_notes": None,
    }
    row.update(overrides)
    return row


def contributor_row(actor: str, repo_name: str, **overrides: object) -> dict[str, object]:
    """One spec 9.4 contributor activity row."""
    row: dict[str, object] = {
        "actor_login": actor,
        "repo_name": repo_name,
        "domain_id": "cloud_devops",
        "subdomains": ["infrastructure_as_code"],
        "push_events": 10,
        "pull_requests_opened": 5,
        "merged_pull_requests_authored": 4,
        "reviews_submitted": 3,
        "issues_opened": 1,
        "issue_comments": 2,
        "active_days": 10,
        "active_months": 3,
        "first_seen": date(2026, 5, 3),
        "last_seen": date(2026, 7, 29),
        "raw_contribution_points": 50.0,
    }
    row.update(overrides)
    return row


def location_row(actor: str, **overrides: object) -> dict[str, object]:
    """One spec 9.6 normalized location row (high-confidence US city default)."""
    row: dict[str, object] = {
        "actor_login": actor,
        "raw_location": "Seattle, WA",
        "normalized_country_code": "US",
        "normalized_country_name": "United States",
        "normalized_city": "Seattle",
        "latitude": None,
        "longitude": None,
        "location_level": "city",
        "location_confidence": "high",
        "normalization_method": "city_country_pair",
        "ambiguity_reason": None,
    }
    row.update(overrides)
    return row


def score_row(actor: str, **overrides: object) -> dict[str, object]:
    """One contributor score row (spec 9.7 fields used by the geography engine)."""
    row: dict[str, object] = {
        "actor_login": actor,
        "domain_id": "cloud_devops",
        "expert_score": 60.0,
        "domain_activity_score": 60.0,
        "contribution_quality_score": 60.0,
        "repository_quality_exposure_score": 60.0,
        "continuity_score": 60.0,
        "collaboration_score": 60.0,
        "qualified_repo_count": 2,
        "active_months": 3,
        "country_code": "US",
        "city": "Seattle",
        "location_confidence": "high",
        "one_repo": False,
        "raw_event_count": 25,
        "weighted_event_points": 50.0,
    }
    row.update(overrides)
    return row


def repo_scores_frame(qualities: dict[str, float]) -> pl.DataFrame:
    """Minimal repository score table for the contributor engine."""
    return pl.DataFrame(
        {
            "repo_name": list(qualities),
            "repository_quality_score": list(qualities.values()),
        }
    )
