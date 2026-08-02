"""Rule-primitive tests: word boundaries, phrase matching, normalization, scoring."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from codetalent import config
from codetalent.classify import rules
from codetalent.config import AtlasConfig
from codetalent.schemas import RepositoryMetadata

REPO_ROOT = Path(__file__).resolve().parents[2]
FETCHED_AT = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def atlas_config() -> AtlasConfig:
    return config.load_all(REPO_ROOT / "config")


def make_metadata(
    repo_name: str,
    *,
    topics: list[str] | None = None,
    description: str | None = None,
    primary_language: str | None = None,
    has_ci: bool | None = None,
) -> RepositoryMetadata:
    return RepositoryMetadata(
        repo_name=repo_name,
        description=description,
        is_fork=False,
        is_archived=False,
        is_disabled=False,
        primary_language=primary_language,
        topics=topics or [],
        stargazer_count=100,
        fork_count=10,
        license_spdx_id="Apache-2.0",
        pushed_at=None,
        updated_at=None,
        release_count=1,
        issue_count=5,
        pull_request_count=5,
        has_readme=True,
        has_contributing=None,
        has_code_of_conduct=None,
        has_ci=has_ci,
        has_tests_signal=None,
        graphql_fetched_at=FETCHED_AT,
    )


class TestTermMatching:
    def test_short_term_never_matches_inside_words(self) -> None:
        assert rules.match_terms("maniac tools for cardiac care", ["iac"]) == ()

    def test_short_term_matches_with_word_boundaries(self) -> None:
        assert rules.match_terms("IaC modules for AWS", ["iac"]) == ("iac",)
        assert rules.match_terms("an iac-scanner utility", ["iac"]) == ("iac",)

    def test_phrase_matches_separator_variants(self) -> None:
        term = ["infrastructure as code"]
        assert rules.match_terms("infrastructure-as-code toolkit", term)
        assert rules.match_terms("Infrastructure_as_Code", term)
        assert rules.match_terms("modern Infrastructure As Code", term)

    def test_phrase_requires_adjacent_words_in_order(self) -> None:
        term = ["infrastructure as code"]
        assert rules.match_terms("infrastructure as codebase", term) == ()
        assert rules.match_terms("code as infrastructure", term) == ()
        assert rules.match_terms("infrastructure codebase", term) == ()

    def test_slash_separated_term(self) -> None:
        assert rules.match_terms("CI/CD pipeline", ["ci/cd"])
        assert rules.match_terms("ci-cd pipeline", ["ci/cd"])
        assert rules.match_terms("ci cd pipeline", ["ci/cd"])
        assert rules.match_terms("circle of decdes", ["ci/cd"]) == ()

    def test_empty_or_missing_text(self) -> None:
        assert rules.match_terms(None, ["terraform"]) == ()
        assert rules.match_terms("", ["terraform"]) == ()

    def test_results_are_sorted_and_deterministic(self) -> None:
        text = "terraform and pulumi provisioning"
        matched = rules.match_terms(text, ["pulumi", "terraform", "provisioning"])
        assert matched == ("provisioning", "pulumi", "terraform")
        assert matched == rules.match_terms(text, ["pulumi", "terraform", "provisioning"])


class TestTopicMatching:
    def test_normalization_variants_match(self) -> None:
        assert rules.match_topics(["Infrastructure_As_Code"], ["infrastructure-as-code"]) == (
            "infrastructure-as-code",
        )
        assert rules.match_topics(["K8S"], ["k8s"]) == ("k8s",)

    def test_topics_never_match_by_substring(self) -> None:
        assert rules.match_topics(["terraforming-mars"], ["terraform"]) == ()
        assert rules.match_topics(["terraform"], ["terraform-provider"]) == ()

    def test_normalize_token(self) -> None:
        assert rules.normalize_token("Infrastructure_As Code") == "infrastructure-as-code"
        assert rules.normalize_token("  Docker--Compose  ") == "docker-compose"


class TestSubdomainScoring:
    def _iac_score(
        self, atlas_config: AtlasConfig, metadata: RepositoryMetadata
    ) -> tuple[float, rules.SubdomainEvidence]:
        taxonomy = atlas_config.taxonomies["cloud_devops"]
        return rules.evaluate_subdomain(
            "infrastructure_as_code",
            taxonomy.subdomains["infrastructure_as_code"],
            metadata,
            atlas_config.scoring.classification,
        )

    def test_topic_match_is_strongest_single_signal(self, atlas_config: AtlasConfig) -> None:
        weights = atlas_config.scoring.classification
        topic_score, topic_evidence = self._iac_score(
            atlas_config, make_metadata("acme/widgets", topics=["pulumi"])
        )
        term_score, term_evidence = self._iac_score(
            atlas_config, make_metadata("acme/widgets", description="works with terragrunt")
        )
        assert topic_score == pytest.approx(weights.topic_weight)
        assert term_score == pytest.approx(weights.term_weight)
        assert topic_score > term_score
        assert topic_evidence.evidence_kinds == 1
        assert term_evidence.evidence_kinds == 1

    def test_distinct_evidence_kinds_compound(self, atlas_config: AtlasConfig) -> None:
        weights = atlas_config.scoring.classification
        score, evidence = self._iac_score(
            atlas_config,
            make_metadata(
                "acme/terraform-widgets",
                topics=["pulumi"],
                description="works with terragrunt",
            ),
        )
        expected = weights.topic_weight + weights.term_weight + weights.name_weight
        assert score == pytest.approx(expected)
        assert evidence.evidence_kinds == 3
        assert evidence.topics == ("pulumi",)
        assert evidence.description_terms == ("terragrunt",)
        assert evidence.name_terms == ("terraform",)

    def test_negative_terms_subtract(self, atlas_config: AtlasConfig) -> None:
        weights = atlas_config.scoring.classification
        score, evidence = self._iac_score(
            atlas_config,
            make_metadata(
                "acme/widgets",
                topics=["pulumi"],
                description="a terragrunt tutorial",
            ),
        )
        expected = weights.topic_weight + weights.term_weight - weights.negative_weight
        assert score == pytest.approx(expected)
        assert evidence.negative_terms == ("tutorial",)

    def test_language_hint_counts_for_iac(self, atlas_config: AtlasConfig) -> None:
        weights = atlas_config.scoring.classification
        score, evidence = self._iac_score(
            atlas_config, make_metadata("acme/modules", primary_language="HCL")
        )
        assert score == pytest.approx(weights.language_weight)
        assert evidence.languages == ("hcl",)

    def test_has_ci_counts_only_for_cicd_subdomain(self, atlas_config: AtlasConfig) -> None:
        weights = atlas_config.scoring.classification
        taxonomy = atlas_config.taxonomies["cloud_devops"]
        metadata = make_metadata("acme/widgets", has_ci=True)
        cicd_score, cicd_evidence = rules.evaluate_subdomain(
            "cicd_developer_tooling",
            taxonomy.subdomains["cicd_developer_tooling"],
            metadata,
            weights,
        )
        iac_score, iac_evidence = self._iac_score(atlas_config, metadata)
        assert cicd_score == pytest.approx(weights.file_weight)
        assert cicd_evidence.files == ("has_ci",)
        assert iac_score == pytest.approx(0.0)
        assert iac_evidence.files == ()

    def test_content_signals_and_language_hints_are_config_driven(
        self, atlas_config: AtlasConfig
    ) -> None:
        # Signal support comes from the taxonomy configuration, not source
        # code: a synthetic subdomain declaring different signals changes the
        # evidence without any code change.
        weights = atlas_config.scoring.classification
        taxonomy = config.SubdomainTaxonomy(
            display_name="Synthetic",
            positive_topics=["nonmatching-topic"],
            positive_terms=["nonmatching term"],
            content_signals=["has_ci", "has_tests_signal"],
            language_hints=["Go"],
        )
        metadata = make_metadata("acme/widgets", primary_language="Go", has_ci=True)
        score, evidence = rules.evaluate_subdomain("synthetic", taxonomy, metadata, weights)
        assert evidence.files == ("has_ci",)  # has_tests_signal is None, not True
        assert evidence.languages == ("go",)
        assert score == pytest.approx(weights.file_weight + weights.language_weight)

    def test_same_inputs_same_outputs(self, atlas_config: AtlasConfig) -> None:
        metadata = make_metadata(
            "acme/terraform-widgets",
            topics=["terraform", "iac"],
            description="Terraform modules with drift detection",
        )
        first = self._iac_score(atlas_config, metadata)
        second = self._iac_score(atlas_config, metadata)
        assert first == second
