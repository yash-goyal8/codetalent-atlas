"""Configuration contract tests against the real files in ``config/``."""

from __future__ import annotations

from pathlib import Path

import pytest

from codetalent import config

EXPECTED_SUBDOMAINS = {
    "infrastructure_as_code",
    "containers_orchestration",
    "cicd_developer_tooling",
    "observability_monitoring",
    "configuration_management",
    "service_mesh_networking",
    "cloud_platforms_sdks",
    "sre_reliability",
}


class TestRealConfigFiles:
    def test_load_all_succeeds(self, config_dir: Path) -> None:
        loaded = config.load_all(config_dir)
        assert "cloud_devops" in loaded.taxonomies

    def test_domains_registry(self, config_dir: Path) -> None:
        domains = config.load_domains(config_dir / "domains.yaml")
        assert domains.domains["cloud_devops"].status is config.DomainStatus.PILOT
        planned = {k for k, v in domains.domains.items() if v.status is config.DomainStatus.PLANNED}
        assert planned == {
            "backend_distributed_systems",
            "systems_engineering_c_cpp",
            "gpu_performance_computing",
            "cybersecurity",
        }

    def test_taxonomy_has_all_eight_subdomains(self, config_dir: Path) -> None:
        taxonomy = config.load_taxonomy(config_dir / "cloud_devops_taxonomy.yaml")
        assert taxonomy.domain_id == "cloud_devops"
        assert set(taxonomy.subdomains) == EXPECTED_SUBDOMAINS

    def test_taxonomy_lists_are_substantial(self, config_dir: Path) -> None:
        taxonomy = config.load_taxonomy(config_dir / "cloud_devops_taxonomy.yaml")
        for name, subdomain in taxonomy.subdomains.items():
            assert len(subdomain.positive_topics) >= 10, name
            assert len(subdomain.positive_terms) >= 8, name
            assert subdomain.negative_terms, name

    def test_repo_filters_match_spec_numbers(self, config_dir: Path) -> None:
        filters = config.load_repo_filters(config_dir / "repo_filters.yaml")
        assert filters.activity_window.pilot_start == "2026-05-01"
        assert filters.activity_window.pilot_end == "2026-07-31"
        assert filters.activity_window.expanded_months == 12
        assert filters.minimums.unique_human_contributors == 5
        assert filters.minimums.meaningful_events == 20
        assert filters.minimums.pull_requests_or_reviews == 3
        assert filters.minimums.active_months == 2
        assert filters.requirements.must_be_public is True
        assert filters.requirements.must_not_be_fork is True
        assert filters.exclusions.single_contributor_dominance_threshold == pytest.approx(0.90)

    def test_event_weights_match_spec(self, config_dir: Path) -> None:
        scoring = config.load_scoring(config_dir / "scoring.yaml")
        weights = scoring.event_weights
        assert weights.merged_pull_request == 5
        assert weights.pull_request_review == 4
        assert weights.pull_request_opened == 3
        assert weights.release == 3
        assert weights.push_event == 2
        assert weights.issue_opened == 1
        assert weights.issue_comment == 1

    def test_all_four_weight_groups_sum_to_one(self, config_dir: Path) -> None:
        scoring = config.load_scoring(config_dir / "scoring.yaml")
        for group in (
            scoring.repository_quality.weights,
            scoring.contributor_expert.weights,
            scoring.opportunity.weights,
            scoring.confidence.weights,
        ):
            assert sum(dict(group).values()) == pytest.approx(1.0, abs=1e-9)

    def test_component_weights_match_spec(self, config_dir: Path) -> None:
        scoring = config.load_scoring(config_dir / "scoring.yaml")
        assert scoring.repository_quality.weights.recent_activity == pytest.approx(0.30)
        assert scoring.repository_quality.winsorization_percentile == pytest.approx(0.99)
        assert scoring.contributor_expert.weights.domain_activity == pytest.approx(0.35)
        assert scoring.contributor_expert.caps.single_repository_share == pytest.approx(0.40)
        assert scoring.contributor_expert.minimums.meaningful_active_days == 2
        assert scoring.opportunity.weights.expert_supply == pytest.approx(0.35)
        assert scoring.confidence.weights.located_profile_coverage == pytest.approx(0.35)

    def test_tier_thresholds_match_spec(self, config_dir: Path) -> None:
        tiers = config.load_scoring(config_dir / "scoring.yaml").tiers
        assert tiers.priority.min_opportunity == 75
        assert tiers.priority.min_confidence == 70
        assert tiers.promising.min_opportunity == 60
        assert tiers.promising.min_confidence == 60
        assert tiers.monitor.min_opportunity == 45
        assert tiers.monitor.confidence_band_min == 45
        assert tiers.monitor.confidence_band_max == 59
        assert tiers.insufficient_data.max_confidence == 45

    def test_minimum_samples_match_spec(self, config_dir: Path) -> None:
        samples = config.load_scoring(config_dir / "scoring.yaml").minimum_samples
        assert samples.country.located_contributors == 30
        assert samples.country.qualified_repositories == 10
        assert samples.country.organizations == 5
        assert samples.city.high_confidence_located_contributors == 25
        assert samples.city.qualified_repositories == 8
        assert samples.city.organizations == 4

    def test_concentration_thresholds_match_spec(self, config_dir: Path) -> None:
        concentration = config.load_scoring(config_dir / "scoring.yaml").concentration
        assert concentration.organization_share_flag == pytest.approx(0.20)
        assert concentration.single_actor_event_share_max == pytest.approx(0.90)

    def test_bot_patterns_cover_spec_minimum(self, config_dir: Path) -> None:
        bots = config.load_bot_patterns(config_dir / "bot_patterns.yaml")
        assert "[bot]" in bots.login_suffixes
        for required in ("dependabot", "renovate", "github-actions", "codecov", "snyk-bot"):
            assert required in bots.exact_logins, required

    def test_location_aliases_load(self, config_dir: Path) -> None:
        aliases = config.load_location_aliases(config_dir / "location_aliases.csv")
        assert len(aliases) >= 15
        by_alias = {a.alias: a for a in aliases}
        assert by_alias["SF"].normalized_city == "San Francisco"
        assert by_alias["UK"].normalized_country_code == "GB"
        assert by_alias["UK"].location_level is config.LocationLevel.COUNTRY

    def test_location_overrides_all_have_notes(self, config_dir: Path) -> None:
        overrides = config.load_location_overrides(config_dir / "location_overrides.csv")
        assert overrides
        for override in overrides:
            assert override.evidence_note.strip()


class TestInvalidConfigFailsLoudly:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(config.ConfigError, match="missing configuration file"):
            config.load_scoring(tmp_path / "scoring.yaml")

    def test_unparseable_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "scoring.yaml"
        bad.write_text("event_weights: [unclosed", encoding="utf-8")
        with pytest.raises(config.ConfigError, match="unparseable YAML"):
            config.load_scoring(bad)

    def test_weights_not_summing_to_one(self, tmp_path: Path, config_dir: Path) -> None:
        original = (config_dir / "scoring.yaml").read_text(encoding="utf-8")
        broken = original.replace("recent_activity: 0.30", "recent_activity: 0.50")
        path = tmp_path / "scoring.yaml"
        path.write_text(broken, encoding="utf-8")
        with pytest.raises(config.ConfigError, match=r"sum to 1\.0"):
            config.load_scoring(path)

    def test_unknown_key_rejected(self, tmp_path: Path, config_dir: Path) -> None:
        original = (config_dir / "repo_filters.yaml").read_text(encoding="utf-8")
        path = tmp_path / "repo_filters.yaml"
        path.write_text(original + "\nextra_section:\n  surprise: true\n", encoding="utf-8")
        with pytest.raises(config.ConfigError):
            config.load_repo_filters(path)

    def test_csv_header_mismatch(self, tmp_path: Path) -> None:
        path = tmp_path / "location_aliases.csv"
        path.write_text("alias,country\nSF,US\n", encoding="utf-8")
        with pytest.raises(config.ConfigError, match="header"):
            config.load_location_aliases(path)

    def test_override_without_note_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "location_overrides.csv"
        path.write_text(
            "raw_location,normalized_country_code,normalized_city,location_level,evidence_note\n"
            "Somewhere,US,,country,\n",
            encoding="utf-8",
        )
        with pytest.raises(config.ConfigError):
            config.load_location_overrides(path)

    def test_pilot_domain_without_taxonomy_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "domains.yaml"
        path.write_text(
            "domains:\n  cloud_devops:\n    display_name: Cloud and DevOps\n    status: pilot\n",
            encoding="utf-8",
        )
        with pytest.raises(config.ConfigError, match="taxonomy_file"):
            config.load_domains(path)

    def test_invalid_bot_regex_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bot_patterns.yaml"
        path.write_text(
            'login_suffixes: ["[bot]"]\nexact_logins: [dependabot]\n'
            'regex_patterns: ["[unclosed"]\n',
            encoding="utf-8",
        )
        with pytest.raises(config.ConfigError, match="invalid bot regex"):
            config.load_bot_patterns(path)
