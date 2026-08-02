"""Known positive/negative classification fixtures driven by the real taxonomy config.

Milestone A-10 deferred obligation: prove the shipped taxonomy accepts
well-known Cloud/DevOps repositories into the right subdomain and rejects the
spec 12 exclusion archetypes with the right negative evidence.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest

from codetalent import config
from codetalent.classify.repository_classifier import (
    classify_repository,
    hard_exclusion_reasons,
    license_is_recognized,
)
from codetalent.config import AtlasConfig
from codetalent.schemas import ClassificationStatus, RepositoryClassification, RepositoryMetadata

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
    license_spdx_id: str | None = "Apache-2.0",
    is_fork: bool = False,
    is_archived: bool = False,
    is_disabled: bool = False,
    has_ci: bool | None = None,
) -> RepositoryMetadata:
    return RepositoryMetadata(
        repo_name=repo_name,
        description=description,
        is_fork=is_fork,
        is_archived=is_archived,
        is_disabled=is_disabled,
        primary_language=primary_language,
        topics=topics or [],
        stargazer_count=1000,
        fork_count=100,
        license_spdx_id=license_spdx_id,
        pushed_at=None,
        updated_at=None,
        release_count=3,
        issue_count=50,
        pull_request_count=40,
        has_readme=True,
        has_contributing=None,
        has_code_of_conduct=None,
        has_ci=has_ci,
        has_tests_signal=None,
        graphql_fetched_at=FETCHED_AT,
    )


def classify(
    atlas_config: AtlasConfig,
    metadata: RepositoryMetadata,
    *,
    share: float | None = 0.2,
    filters: config.RepoFiltersConfig | None = None,
) -> RepositoryClassification:
    return classify_repository(
        metadata,
        atlas_config.taxonomies["cloud_devops"],
        atlas_config.scoring.classification,
        filters=filters if filters is not None else atlas_config.repo_filters,
        single_actor_event_share=share,
    )


# (expected_subdomain, metadata) — three known positives per subdomain,
# modeled on real flagship repositories of each ecosystem.
POSITIVE_FIXTURES: list[tuple[str, RepositoryMetadata]] = [
    (
        "infrastructure_as_code",
        make_metadata(
            "hashicorp/terraform",
            topics=["terraform", "infrastructure-as-code", "golang"],
            description=(
                "Terraform enables you to safely and predictably create, change, "
                "and improve infrastructure"
            ),
            primary_language="Go",
        ),
    ),
    (
        "infrastructure_as_code",
        make_metadata(
            "pulumi/pulumi",
            topics=["pulumi", "infrastructure-as-code", "iac", "aws", "azure"],
            description="Pulumi - Infrastructure as Code SDK in any programming language",
            primary_language="Go",
        ),
    ),
    (
        "infrastructure_as_code",
        make_metadata(
            "opentofu/opentofu",
            topics=["opentofu", "terraform", "infrastructure-as-code"],
            description=(
                "OpenTofu lets you declaratively manage your cloud infrastructure "
                "with infrastructure as code"
            ),
            primary_language="Go",
        ),
    ),
    (
        "containers_orchestration",
        make_metadata(
            "kubernetes/kubernetes",
            topics=["kubernetes", "containers", "cncf"],
            description="Production-Grade Container Scheduling and Management",
            primary_language="Go",
        ),
    ),
    (
        "containers_orchestration",
        make_metadata(
            "helm/helm",
            topics=["helm", "kubernetes", "charts"],
            description="The Kubernetes Package Manager",
            primary_language="Go",
        ),
    ),
    (
        "containers_orchestration",
        make_metadata(
            "containerd/containerd",
            topics=["containerd", "containers", "oci", "docker"],
            description="An open and reliable container runtime",
            primary_language="Go",
        ),
    ),
    (
        "cicd_developer_tooling",
        make_metadata(
            "argoproj/argo-cd",
            topics=["argocd", "gitops", "kubernetes", "continuous-delivery", "cicd"],
            description="Declarative Continuous Deployment for Kubernetes",
            primary_language="Go",
        ),
    ),
    (
        "cicd_developer_tooling",
        make_metadata(
            "jenkinsci/jenkins",
            topics=["jenkins", "continuous-integration", "cicd", "devops"],
            description="Jenkins automation server",
            primary_language="Java",
        ),
    ),
    (
        "cicd_developer_tooling",
        make_metadata(
            "bazelbuild/bazel",
            topics=["bazel", "build-system", "developer-tools"],
            description="a fast, scalable, multi-language and extensible build system",
            primary_language="Java",
        ),
    ),
    (
        "observability_monitoring",
        make_metadata(
            "prometheus/prometheus",
            topics=["prometheus", "monitoring", "metrics", "alerting"],
            description="The Prometheus monitoring system and time series database",
            primary_language="Go",
        ),
    ),
    (
        "observability_monitoring",
        make_metadata(
            "grafana/grafana",
            topics=["grafana", "monitoring", "observability", "dashboards"],
            description="The open and composable observability and data visualization platform",
            primary_language="TypeScript",
        ),
    ),
    (
        "observability_monitoring",
        make_metadata(
            "open-telemetry/opentelemetry-collector",
            topics=["opentelemetry", "observability", "tracing", "metrics", "monitoring"],
            description="OpenTelemetry Collector",
            primary_language="Go",
        ),
    ),
    (
        "configuration_management",
        make_metadata(
            "ansible/ansible",
            topics=["ansible", "python", "configuration-management"],
            description=(
                "Ansible is a radically simple IT automation platform that handles "
                "configuration management and application deployment"
            ),
            primary_language="Python",
        ),
    ),
    (
        "configuration_management",
        make_metadata(
            "puppetlabs/puppet",
            topics=["puppet", "configuration-management"],
            description="Server automation framework and application",
            primary_language="Ruby",
        ),
    ),
    (
        "configuration_management",
        make_metadata(
            "NixOS/nixpkgs",
            topics=["nix", "nixos", "linux"],
            description="Nix Packages collection & NixOS",
            primary_language="Nix",
        ),
    ),
    (
        "service_mesh_networking",
        make_metadata(
            "istio/istio",
            topics=["istio", "service-mesh", "kubernetes", "envoy"],
            description=(
                "Connect, secure, control, and observe services with the Istio service mesh"
            ),
            primary_language="Go",
        ),
    ),
    (
        "service_mesh_networking",
        make_metadata(
            "envoyproxy/envoy",
            topics=["envoy", "proxy", "service-mesh", "load-balancer"],
            description="Cloud-native high-performance edge/middle/service proxy",
            primary_language="C++",
        ),
    ),
    (
        "service_mesh_networking",
        make_metadata(
            "cilium/cilium",
            topics=["cilium", "ebpf", "kubernetes", "networking", "cni"],
            description="eBPF-based Networking, Security, and Observability",
            primary_language="Go",
        ),
    ),
    (
        "cloud_platforms_sdks",
        make_metadata(
            "boto/boto3",
            topics=["aws", "boto3", "python", "cloud"],
            description="AWS SDK for Python",
            primary_language="Python",
        ),
    ),
    (
        "cloud_platforms_sdks",
        make_metadata(
            "serverless/serverless",
            topics=["serverless", "aws-lambda", "aws", "faas"],
            description=(
                "Serverless Framework - Build applications on AWS Lambda and other "
                "next-gen cloud services"
            ),
            primary_language="JavaScript",
        ),
    ),
    (
        "cloud_platforms_sdks",
        make_metadata(
            "Azure/azure-sdk-for-go",
            topics=["azure", "azure-sdk", "golang"],
            description="This repository is for active development of the Azure SDK for Go",
            primary_language="Go",
        ),
    ),
    (
        "sre_reliability",
        make_metadata(
            "chaos-mesh/chaos-mesh",
            topics=["chaos-engineering", "chaos-mesh", "kubernetes", "fault-injection"],
            description="A Chaos Engineering Platform for Kubernetes",
            primary_language="Go",
        ),
    ),
    (
        "sre_reliability",
        make_metadata(
            "grafana/oncall",
            topics=["oncall", "incident-response", "sre"],
            description="Developer-friendly incident response with brilliant Slack integration",
            primary_language="Python",
        ),
    ),
    (
        "sre_reliability",
        make_metadata(
            "monzo/response",
            topics=["incident-response", "sre", "slack"],
            description="Monzo's real-time incident response and reporting tool",
            primary_language="Python",
        ),
    ),
]


class TestKnownPositives:
    def test_fixture_coverage_three_per_subdomain(self, atlas_config: AtlasConfig) -> None:
        counts = Counter(expected for expected, _ in POSITIVE_FIXTURES)
        taxonomy = atlas_config.taxonomies["cloud_devops"]
        for subdomain_id in taxonomy.subdomains:
            assert counts[subdomain_id] >= 3, subdomain_id

    @pytest.mark.parametrize(
        ("expected_subdomain", "metadata"),
        POSITIVE_FIXTURES,
        ids=[metadata.repo_name for _, metadata in POSITIVE_FIXTURES],
    )
    def test_known_positive_accepted_with_correct_subdomain(
        self,
        atlas_config: AtlasConfig,
        expected_subdomain: str,
        metadata: RepositoryMetadata,
    ) -> None:
        result = classify(atlas_config, metadata)
        assert result.classification_status is ClassificationStatus.ACCEPTED
        assert expected_subdomain in result.subdomains
        assert result.classification_score >= atlas_config.scoring.classification.accept_threshold
        assert result.evidence_topics or result.evidence_terms

    def test_min_evidence_kinds_blocks_single_kind_subdomain(
        self, atlas_config: AtlasConfig
    ) -> None:
        # pulumi/pulumi carries aws+azure topics but no cloud terms: the
        # cloud subdomain has one evidence kind only and must not be listed.
        _, metadata = POSITIVE_FIXTURES[1]
        result = classify(atlas_config, metadata)
        assert result.subdomains == ["infrastructure_as_code"]
        assert "cloud_platforms_sdks" not in result.subdomains


class TestKnownNegatives:
    def test_awesome_list_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "sindresorhus/awesome-devops",
                topics=["awesome", "awesome-list", "devops"],
                description="A curated list of awesome DevOps tools and resources",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:awesome_list" in result.negative_evidence
        assert result.subdomains == []
        assert result.classification_score == 0.0

    def test_tutorial_rejected_despite_kubernetes_evidence(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/kubernetes-tutorial",
                topics=["kubernetes", "tutorial"],
                description="Step by step Kubernetes tutorial for beginners",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:tutorial" in result.negative_evidence
        assert result.subdomains == []
        assert result.classification_score == 0.0

    def test_interview_prep_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/devops-interview-questions",
                description="DevOps interview questions and answers",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:interview_prep" in result.negative_evidence

    def test_dotfiles_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "jdoe/dotfiles",
                description="My personal dotfiles managed with ansible",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:dotfiles" in result.negative_evidence
        assert result.subdomains == []

    def test_student_course_code_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "team4/cse110-final-project",
                description="Final project for CSE110 at UCSD",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:student_assignment" in result.negative_evidence

    def test_docs_only_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata("acme/docs", description="Documentation for the Acme platform"),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:documentation_only" in result.negative_evidence

    def test_unrelated_react_todo_rejected_without_evidence(
        self, atlas_config: AtlasConfig
    ) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "jdoe/react-todo-app",
                topics=["react", "javascript", "todo"],
                description="A simple todo list application built with React",
                primary_language="JavaScript",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert result.subdomains == []
        assert result.evidence_topics == []
        assert result.negative_evidence == []
        border = atlas_config.scoring.classification.borderline_threshold
        assert result.classification_score < border

    def test_archived_rejected_despite_strong_evidence(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/terraform-modules",
                topics=["terraform", "infrastructure-as-code"],
                description="Production Terraform modules",
                is_archived=True,
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:archived" in result.negative_evidence
        assert result.subdomains == []
        assert result.classification_score == 0.0

    def test_fork_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata("jdoe/kubernetes", topics=["kubernetes"], is_fork=True),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:fork" in result.negative_evidence

    def test_disabled_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata("acme/old-tool", topics=["terraform"], is_disabled=True),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:disabled" in result.negative_evidence

    def test_single_actor_dominance_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/solo-iac",
                topics=["terraform", "infrastructure-as-code"],
                description="Terraform modules",
            ),
            share=0.95,
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:single_actor_dominance" in result.negative_evidence

    def test_dominance_threshold_is_strict(self, atlas_config: AtlasConfig) -> None:
        # exactly at the 0.90 threshold means "not more than", so no exclusion
        result = classify(
            atlas_config,
            make_metadata(
                "acme/edge-proxy",
                topics=["envoy", "proxy", "service-mesh"],
                description="A reverse proxy for edge networking",
            ),
            share=0.90,
        )
        assert result.classification_status is ClassificationStatus.ACCEPTED
        assert "service_mesh_networking" in result.subdomains

    def test_noassertion_license_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/mesh-router",
                topics=["envoy", "service-mesh"],
                description="Sidecar proxy for the mesh",
                license_spdx_id="NOASSERTION",
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:license" in result.negative_evidence

    def test_missing_license_rejected(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/cloud-tool",
                topics=["aws"],
                description="CLI for AWS",
                license_spdx_id=None,
            ),
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        assert "exclusion:license" in result.negative_evidence


class TestBorderline:
    def test_weak_term_only_repo_is_borderline(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "acme/terraform-helper",
                description="Helper scripts for Terraform state cleanup",
            ),
        )
        assert result.classification_status is ClassificationStatus.BORDERLINE
        assert "infrastructure_as_code" in result.subdomains

    def test_strong_score_with_single_evidence_kind_is_borderline(
        self, atlas_config: AtlasConfig
    ) -> None:
        result = classify(
            atlas_config,
            make_metadata("acme/orchestrator", topics=["kubernetes", "docker"]),
        )
        assert result.classification_status is ClassificationStatus.BORDERLINE
        assert "containers_orchestration" in result.subdomains


class TestRepoFilterFlagGating:
    """Spec 8.2 contract: every requirement/exclusion flag really gates its check."""

    @staticmethod
    def _with_flags(
        atlas_config: AtlasConfig,
        *,
        requirements: dict[str, bool] | None = None,
        exclusions: dict[str, bool] | None = None,
    ) -> config.RepoFiltersConfig:
        filters = atlas_config.repo_filters
        updates: dict[str, object] = {}
        if requirements:
            updates["requirements"] = filters.requirements.model_copy(update=requirements)
        if exclusions:
            updates["exclusions"] = filters.exclusions.model_copy(update=exclusions)
        return filters.model_copy(update=updates)

    def test_tutorial_only_false_disables_tutorial_exclusion(
        self, atlas_config: AtlasConfig
    ) -> None:
        metadata = make_metadata(
            "acme/kubernetes-tutorial",
            topics=["kubernetes"],
            description="Step by step Kubernetes tutorial for beginners",
        )
        default = classify(atlas_config, metadata)
        assert "exclusion:tutorial" in default.negative_evidence
        relaxed = classify(
            atlas_config,
            metadata,
            filters=self._with_flags(atlas_config, exclusions={"tutorial_only": False}),
        )
        assert "exclusion:tutorial" not in relaxed.negative_evidence
        assert relaxed.classification_score > 0.0

    def test_must_not_be_fork_false_disables_fork_exclusion(
        self, atlas_config: AtlasConfig
    ) -> None:
        metadata = make_metadata("jdoe/kubernetes", topics=["kubernetes"], is_fork=True)
        relaxed = self._with_flags(atlas_config, requirements={"must_not_be_fork": False})
        reasons = hard_exclusion_reasons(metadata, filters=relaxed, single_actor_event_share=0.1)
        assert reasons == []

    def test_require_recognized_license_false_disables_license_exclusion(
        self, atlas_config: AtlasConfig
    ) -> None:
        metadata = make_metadata("acme/mesh-router", license_spdx_id=None)
        relaxed = self._with_flags(atlas_config, requirements={"require_recognized_license": False})
        reasons = hard_exclusion_reasons(metadata, filters=relaxed, single_actor_event_share=0.1)
        assert reasons == []

    @pytest.mark.parametrize(
        ("flag", "repo_name", "tag"),
        [
            ("dotfiles", "jdoe/dotfiles", "dotfiles"),
            ("student_assignments", "team4/cse110-labs", "student_assignment"),
            ("interview_prep", "acme/devops-interview-questions", "interview_prep"),
            ("awesome_lists", "jdoe/awesome-devops", "awesome_list"),
            ("documentation_only", "acme/docs", "documentation_only"),
        ],
    )
    def test_each_pattern_exclusion_flag_gates_its_check(
        self, atlas_config: AtlasConfig, flag: str, repo_name: str, tag: str
    ) -> None:
        metadata = make_metadata(repo_name)
        enabled = hard_exclusion_reasons(
            metadata, filters=atlas_config.repo_filters, single_actor_event_share=0.1
        )
        assert f"exclusion:{tag}" in enabled
        relaxed = self._with_flags(atlas_config, exclusions={flag: False})
        disabled = hard_exclusion_reasons(metadata, filters=relaxed, single_actor_event_share=0.1)
        assert f"exclusion:{tag}" not in disabled


class TestLicenseAndExclusionPrimitives:
    def test_recognized_licenses(self) -> None:
        assert license_is_recognized("MIT")
        assert license_is_recognized("Apache-2.0")
        assert license_is_recognized("GPL-3.0")
        assert license_is_recognized("mit")  # case-insensitive

    def test_unrecognized_licenses(self) -> None:
        assert not license_is_recognized("NOASSERTION")
        assert not license_is_recognized(None)
        assert not license_is_recognized("Proprietary")

    def test_legit_tool_names_are_not_excluded(self, atlas_config: AtlasConfig) -> None:
        # conservative patterns: real tools must never be name-excluded —
        # including letters+digits names (CVE ids, RFC numbers, ES years,
        # hash/cipher names) that superficially resemble course codes
        for repo_name in (
            "terraform-docs/terraform-docs",
            "k3s-io/k3s",
            "acme/base64-tools",
            "acme/cve-2021-44228-scanner",
            "acme/rfc-3339-parser",
            "acme/es2015-config",
            "acme/sha256-verify",
        ):
            reasons = hard_exclusion_reasons(
                make_metadata(repo_name),
                filters=atlas_config.repo_filters,
                single_actor_event_share=0.1,
            )
            assert reasons == [], repo_name

    def test_course_codes_still_excluded_by_tightened_pattern(
        self, atlas_config: AtlasConfig
    ) -> None:
        for repo_name in ("team4/cse110-final-project", "jdoe/swp391", "uni/comp3120_labs"):
            reasons = hard_exclusion_reasons(
                make_metadata(repo_name),
                filters=atlas_config.repo_filters,
                single_actor_event_share=0.1,
            )
            assert reasons == ["exclusion:student_assignment"], repo_name

    def test_score_comes_from_listed_subdomains_only(self, atlas_config: AtlasConfig) -> None:
        # observability_monitoring earns 5 topic matches (one evidence kind, so
        # it fails the min_evidence_kinds gate and is not listed) while
        # infrastructure_as_code is accepted with topic + name evidence. The
        # recorded score must come from the listed subdomain, never from the
        # unlisted high scorer, so the record stays auditable from its evidence.
        result = classify(
            atlas_config,
            make_metadata(
                "acme/terraform-thing",
                topics=["prometheus", "grafana", "loki", "jaeger", "monitoring", "terraform"],
            ),
        )
        assert result.classification_status is ClassificationStatus.ACCEPTED
        assert result.subdomains == ["infrastructure_as_code"]
        weights = atlas_config.scoring.classification
        assert result.classification_score == pytest.approx(
            weights.topic_weight + weights.name_weight
        )

    def test_multiple_reasons_recorded(self, atlas_config: AtlasConfig) -> None:
        result = classify(
            atlas_config,
            make_metadata(
                "jdoe/awesome-kubernetes",
                description="A curated list of awesome Kubernetes tutorials",
                is_fork=True,
                license_spdx_id=None,
            ),
            share=0.95,
        )
        assert result.classification_status is ClassificationStatus.REJECTED
        for reason in (
            "exclusion:fork",
            "exclusion:license",
            "exclusion:single_actor_dominance",
            "exclusion:awesome_list",
            "exclusion:tutorial",
        ):
            assert reason in result.negative_evidence, reason
