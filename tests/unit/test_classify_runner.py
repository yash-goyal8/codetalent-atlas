"""Runner round-trip: synthetic metadata + activity parquet -> spec 9.3 parquet."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from codetalent import config
from codetalent.classify.runner import ClassificationRunSummary, classify_repositories
from codetalent.config import AtlasConfig, ConfigError
from codetalent.schemas import RepositoryClassification

REPO_ROOT = Path(__file__).resolve().parents[2]
FETCHED_AT = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def atlas_config() -> AtlasConfig:
    return config.load_all(REPO_ROOT / "config")


def metadata_row(
    repo_name: str,
    *,
    topics: list[str] | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        "repo_name": repo_name,
        "description": description,
        "is_fork": False,
        "is_archived": False,
        "is_disabled": False,
        "primary_language": "Go",
        "topics": topics or [],
        "stargazer_count": 500,
        "fork_count": 50,
        "license_spdx_id": "Apache-2.0",
        "pushed_at": datetime(2026, 7, 20, tzinfo=UTC),
        "updated_at": None,
        "release_count": 2,
        "issue_count": 20,
        "pull_request_count": 15,
        "has_readme": True,
        "has_contributing": None,
        "has_code_of_conduct": None,
        "has_ci": True,
        "has_tests_signal": None,
        "graphql_fetched_at": FETCHED_AT,
    }


_METADATA_SCHEMA = pa.schema(
    [
        pa.field("repo_name", pa.string()),
        pa.field("description", pa.string()),
        pa.field("is_fork", pa.bool_()),
        pa.field("is_archived", pa.bool_()),
        pa.field("is_disabled", pa.bool_()),
        pa.field("primary_language", pa.string()),
        pa.field("topics", pa.list_(pa.string())),
        pa.field("stargazer_count", pa.int64()),
        pa.field("fork_count", pa.int64()),
        pa.field("license_spdx_id", pa.string()),
        pa.field("pushed_at", pa.timestamp("us", tz="UTC")),
        pa.field("updated_at", pa.timestamp("us", tz="UTC")),
        pa.field("release_count", pa.int64()),
        pa.field("issue_count", pa.int64()),
        pa.field("pull_request_count", pa.int64()),
        pa.field("has_readme", pa.bool_()),
        pa.field("has_contributing", pa.bool_()),
        pa.field("has_code_of_conduct", pa.bool_()),
        pa.field("has_ci", pa.bool_()),
        pa.field("has_tests_signal", pa.bool_()),
        pa.field("graphql_fetched_at", pa.timestamp("us", tz="UTC")),
    ]
)


def write_fixture_parquets(tmp_path: Path) -> tuple[Path, Path]:
    metadata_rows = [
        metadata_row(
            "acme/terraform-widgets",
            topics=["terraform", "infrastructure-as-code"],
            description="Terraform modules for widget infrastructure",
        ),
        metadata_row("acme/todo-web", topics=["react"], description="A todo web app"),
        metadata_row(
            "acme/terraform-helper",
            description="Helper scripts for Terraform state cleanup",
        ),
        metadata_row(
            "acme/awesome-devops",
            description="A curated list of awesome DevOps tools",
        ),
        metadata_row("acme/solo-tool", topics=["terraform"], description="Terraform tooling"),
    ]
    metadata_path = tmp_path / "repository_metadata.parquet"
    pq.write_table(pa.Table.from_pylist(metadata_rows, schema=_METADATA_SCHEMA), metadata_path)

    # activity summary: extra columns and extra repos must be tolerated;
    # acme/todo-web is deliberately missing (no dominance data available).
    activity_rows = [
        {"repo_name": "acme/terraform-widgets", "single_actor_event_share": 0.30, "extra": 1.0},
        {"repo_name": "acme/terraform-helper", "single_actor_event_share": 0.50, "extra": 1.0},
        {"repo_name": "acme/awesome-devops", "single_actor_event_share": 0.10, "extra": 1.0},
        {"repo_name": "acme/solo-tool", "single_actor_event_share": 0.95, "extra": 1.0},
        {"repo_name": "acme/unrelated", "single_actor_event_share": 0.20, "extra": 1.0},
    ]
    activity_path = tmp_path / "repository_activity_summary.parquet"
    pq.write_table(pa.Table.from_pylist(activity_rows), activity_path)
    return metadata_path, activity_path


class TestClassifyRepositories:
    def test_round_trip(self, atlas_config: AtlasConfig, tmp_path: Path) -> None:
        metadata_path, activity_path = write_fixture_parquets(tmp_path)
        output_path = tmp_path / "out" / "cloud_devops_repository_classification.parquet"

        summary = classify_repositories(
            atlas_config, "cloud_devops", metadata_path, activity_path, output_path
        )

        assert isinstance(summary, ClassificationRunSummary)
        assert summary.total == 5
        assert summary.accepted == 1
        assert summary.borderline == 1
        assert summary.rejected == 3
        assert summary.output_path == output_path
        assert output_path.is_file()

        rows = pq.read_table(output_path).to_pylist()
        assert [row["repo_name"] for row in rows] == sorted(row["repo_name"] for row in rows)
        records = [RepositoryClassification.model_validate(row) for row in rows]
        by_repo = {record.repo_name: record for record in records}

        assert by_repo["acme/terraform-widgets"].classification_status.value == "accepted"
        assert "infrastructure_as_code" in by_repo["acme/terraform-widgets"].subdomains
        assert by_repo["acme/terraform-helper"].classification_status.value == "borderline"
        assert by_repo["acme/todo-web"].classification_status.value == "rejected"
        assert by_repo["acme/awesome-devops"].classification_status.value == "rejected"
        assert "exclusion:awesome_list" in by_repo["acme/awesome-devops"].negative_evidence
        assert by_repo["acme/solo-tool"].classification_status.value == "rejected"
        assert "exclusion:single_actor_dominance" in by_repo["acme/solo-tool"].negative_evidence
        for record in records:
            assert record.domain_id == "cloud_devops"
            assert record.manual_label is None
            assert record.manual_notes is None

    def test_deterministic_across_runs(self, atlas_config: AtlasConfig, tmp_path: Path) -> None:
        metadata_path, activity_path = write_fixture_parquets(tmp_path)
        first_path = tmp_path / "first.parquet"
        second_path = tmp_path / "second.parquet"
        classify_repositories(
            atlas_config, "cloud_devops", metadata_path, activity_path, first_path
        )
        classify_repositories(
            atlas_config, "cloud_devops", metadata_path, activity_path, second_path
        )
        assert pq.read_table(first_path).to_pylist() == pq.read_table(second_path).to_pylist()

    def test_unknown_domain_fails_loudly(self, atlas_config: AtlasConfig, tmp_path: Path) -> None:
        metadata_path, activity_path = write_fixture_parquets(tmp_path)
        with pytest.raises(ConfigError, match="unknown domain_id"):
            classify_repositories(
                atlas_config, "nope", metadata_path, activity_path, tmp_path / "out.parquet"
            )

    def test_output_columns_match_spec_order(
        self, atlas_config: AtlasConfig, tmp_path: Path
    ) -> None:
        metadata_path, activity_path = write_fixture_parquets(tmp_path)
        output_path = tmp_path / "out.parquet"
        classify_repositories(
            atlas_config, "cloud_devops", metadata_path, activity_path, output_path
        )
        schema = pq.read_schema(output_path)
        assert schema.names == list(RepositoryClassification.model_fields)
