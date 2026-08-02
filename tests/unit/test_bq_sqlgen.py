"""SQL template rendering tests: strict placeholders, escaping, config injection.

Uses the real configuration contracts in ``config/`` and the real templates in
``sql/`` so drift between them fails loudly. No BigQuery access anywhere.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from codetalent.bigquery import dry_run, sqlgen
from codetalent.config import AtlasConfig, load_all
from codetalent.settings import Settings

SQL_FILES = [
    "00_profile_tables.sql",
    "01_extract_events.sql",
    "02_remove_bots.sql",
    "03_aggregate_repositories.sql",
    "04_apply_activity_filters.sql",
    "05_extract_contributor_activity.sql",
    "06_quality_checks.sql",
]

# SELECT * or an alias star (e.g. "repo.*"); \w before the dot avoids false
# positives on ".*" inside rendered regex literals like r'.*\[bot\]$'.
SELECT_STAR = re.compile(r"SELECT\s+\*|\w\.\*", re.IGNORECASE)


@pytest.fixture
def config(repo_root: Path) -> AtlasConfig:
    return load_all(repo_root / "config")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        google_cloud_project="test-project",
    )


@pytest.fixture
def plan(config: AtlasConfig, settings: Settings, repo_root: Path) -> list[dry_run.QuerySpec]:
    return dry_run.build_discovery_plan(
        config=config,
        settings=settings,
        domain_id="cloud_devops",
        start=date(2026, 5, 1),
        end=date(2026, 7, 31),
        sql_dir=repo_root / "sql",
    )


class TestTemplates:
    @pytest.mark.parametrize("filename", SQL_FILES)
    def test_every_template_parses_into_statements(self, repo_root: Path, filename: str) -> None:
        statements = sqlgen.load_statements(repo_root / "sql" / filename)
        assert statements
        for sql in statements.values():
            assert sql.strip()

    @pytest.mark.parametrize("filename", SQL_FILES)
    def test_no_select_star_in_templates(self, repo_root: Path, filename: str) -> None:
        for sql in sqlgen.load_statements(repo_root / "sql" / filename).values():
            assert not SELECT_STAR.search(sql), f"SELECT * (or alias.*) found in {filename}"


class TestRenderStatement:
    def test_substitutes_all_placeholders(self) -> None:
        rendered = sqlgen.render_statement("SELECT {a} FROM {b}", {"a": "x", "b": "t"})
        assert rendered == "SELECT x FROM t"

    def test_missing_parameter_is_an_error(self) -> None:
        with pytest.raises(sqlgen.SqlRenderError, match="unrendered"):
            sqlgen.render_statement("SELECT {a} FROM {b}", {"a": "x"})

    def test_unused_parameter_is_an_error(self) -> None:
        with pytest.raises(sqlgen.SqlRenderError, match="unused"):
            sqlgen.render_statement("SELECT {a}", {"a": "x", "extra": "y"})

    def test_values_are_not_rescanned_for_placeholders(self) -> None:
        rendered = sqlgen.render_statement("SELECT {a}", {"a": "'{not_a_placeholder}'"})
        assert rendered == "SELECT '{not_a_placeholder}'"


class TestEscaping:
    def test_string_literal_escapes_quotes_and_backslashes(self) -> None:
        assert sqlgen.sql_string_literal("a'b") == "'a\\'b'"
        assert sqlgen.sql_string_literal("a\\b") == "'a\\\\b'"

    def test_string_literal_rejects_control_characters(self) -> None:
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.sql_string_literal("a\nb")

    def test_raw_regex_literal_keeps_backslashes(self) -> None:
        assert sqlgen.sql_raw_regex_literal(r".*\[bot\]$") == r"r'.*\[bot\]$'"

    def test_raw_regex_literal_rejects_quotes_and_bad_patterns(self) -> None:
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.sql_raw_regex_literal("it's")
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.sql_raw_regex_literal("([unclosed")

    def test_identifier_validation(self) -> None:
        assert sqlgen.validate_identifier("codetalent-atlas") == "codetalent-atlas"
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.validate_identifier("bad.name")
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.validate_identifier("bad name")

    def test_number_rendering(self) -> None:
        assert sqlgen.sql_number(5) == "5"
        assert sqlgen.sql_number(0.25) == "0.25"
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.sql_number(float("inf"))


class TestBotPatternCase:
    def test_suffix_exact_substring_and_regex_branches(self, config: AtlasConfig) -> None:
        case = sqlgen.bot_pattern_case(config.bot_patterns)
        # [bot] suffix: matched case-insensitively, label records the pattern.
        assert "ENDS_WITH(LOWER(actor_login), '[bot]')" in case
        assert "'login_suffix:[bot]'" in case
        # Exact logins each get their own branch for per-pattern audit counts.
        assert "WHEN LOWER(actor_login) = 'dependabot' THEN 'exact_login:dependabot'" in case
        # Substrings.
        assert "STRPOS(LOWER(actor_login), 'renovate') > 0" in case
        # Regexes are raw literals with backslash escaping intact.
        assert r"REGEXP_CONTAINS(LOWER(actor_login), r'.*\[bot\]$')" in case
        assert case.strip().startswith("CASE")
        assert case.strip().endswith("END")

    def test_every_configured_pattern_appears(self, config: AtlasConfig) -> None:
        case = sqlgen.bot_pattern_case(config.bot_patterns)
        patterns = config.bot_patterns
        for login in patterns.exact_logins:
            assert f"exact_login:{login}" in case
        for substring in patterns.substring_patterns:
            assert f"substring:{substring}" in case
        for regex in patterns.regex_patterns:
            # Labels pass through sql_string_literal, which escapes backslashes,
            # so compare against the rendered literal rather than the raw text.
            assert sqlgen.sql_string_literal(f"regex:{regex}") in case


class TestTaxonomyPredicate:
    def test_terms_are_normalized_variants(self, config: AtlasConfig) -> None:
        terms = sqlgen.taxonomy_name_terms(config.taxonomies["cloud_devops"])
        assert "terraform" in terms
        # Multi-word terms produce hyphenated and concatenated variants.
        assert "infrastructure-as-code" in terms
        assert "infrastructureascode" in terms
        assert all(len(term) >= sqlgen.MIN_TAXONOMY_TERM_LENGTH for term in terms)
        assert terms == sorted(terms)

    def test_predicate_is_bounded_regex(self, config: AtlasConfig) -> None:
        predicate = sqlgen.taxonomy_match_predicate(
            config.taxonomies["cloud_devops"], column="r.repo_name"
        )
        assert predicate.startswith("REGEXP_CONTAINS(LOWER(r.repo_name), r'")
        assert "(^|[^a-z0-9])" in predicate
        assert "($|[^a-z0-9])" in predicate
        # The embedded alternation must compile as a regex.
        inner = predicate.split("r'", 1)[1].rsplit("'", 1)[0]
        compiled = re.compile(inner)
        assert compiled.search("owner/terraform-provider-foo")
        assert compiled.search("kubernetes/kubernetes")
        assert not compiled.search("owner/basalt")  # 'salt' must be bounded


class TestGridFragments:
    def test_grid_union_lists_explicit_columns_per_month(self) -> None:
        union = sqlgen.grid_union("proj", "ds", ["202605", "202606"])
        assert union.count("UNION ALL") == 1
        assert "`proj.ds.events_grid_202605`" in union
        assert "`proj.ds.events_grid_202606`" in union
        for column in sqlgen.GRID_COLUMNS:
            assert column in union
        assert "SELECT *" not in union

    def test_grid_duplicate_total_sums_all_months(self) -> None:
        fragment = sqlgen.grid_duplicate_total("proj", "ds", ["202605", "202606", "202607"])
        assert fragment.count("HAVING COUNT(*) > 1") == 3
        assert fragment.count("+") == 2

    def test_invalid_month_rejected(self) -> None:
        with pytest.raises(sqlgen.SqlRenderError):
            sqlgen.grid_union("proj", "ds", ["2026-05"])


class TestDiscoveryPlanRendering:
    def test_plan_has_expected_order_and_names(self, plan: list[dry_run.QuerySpec]) -> None:
        assert [spec.name for spec in plan] == [
            "extract_events_202605",
            "extract_events_202606",
            "extract_events_202607",
            "bot_exclusion_audit",
            "human_grid_view",
            "aggregate_repositories_cloud_devops",
            "apply_activity_filters_cloud_devops",
            "extract_contributor_activity_cloud_devops",
            "quality_checks",
        ]

    def test_no_unrendered_placeholders_or_select_star(self, plan: list[dry_run.QuerySpec]) -> None:
        for spec in plan:
            assert not re.search(r"\{[a-z0-9_]+\}", spec.sql), spec.name
            assert not SELECT_STAR.search(spec.sql), spec.name

    def test_event_weights_come_from_config(
        self, plan: list[dry_run.QuerySpec], config: AtlasConfig
    ) -> None:
        weights = config.scoring.event_weights
        aggregate = next(s for s in plan if s.name == "aggregate_repositories_cloud_devops")
        contributor = next(s for s in plan if s.name == "extract_contributor_activity_cloud_devops")
        for sql, merged_column in (
            (aggregate.sql, "r.prs_merged"),
            (contributor.sql, "SUM(e.prs_merged)"),
        ):
            merged_weight = sqlgen.sql_number(weights.merged_pull_request)
            assert f"CAST({merged_column} AS FLOAT64) * {merged_weight}" in sql
            assert f"* {sqlgen.sql_number(weights.pull_request_review)}" in sql
            assert f"* {sqlgen.sql_number(weights.issue_comment)}" in sql

    def test_filter_thresholds_come_from_config(
        self, plan: list[dry_run.QuerySpec], config: AtlasConfig
    ) -> None:
        minimums = config.repo_filters.minimums
        filters = next(s for s in plan if s.name == "apply_activity_filters_cloud_devops")
        # Minimums render as failed-minimum checks (`field < threshold`) whose
        # reason labels feed exclusion_reason; assert the config values landed.
        assert f"unique_human_contributors < {minimums.unique_human_contributors}" in filters.sql
        assert f"meaningful_events < {minimums.meaningful_events}" in filters.sql
        assert f"pull_requests_or_reviews < {minimums.pull_requests_or_reviews}" in filters.sql
        assert f"active_months < {minimums.active_months}" in filters.sql

    def test_grid_query_targets_six_event_types_and_payload_fallback(
        self, plan: list[dry_run.QuerySpec]
    ) -> None:
        grid = next(s for s in plan if s.name == "extract_events_202605")
        for event_type in (
            "PushEvent",
            "PullRequestEvent",
            "PullRequestReviewEvent",
            "IssuesEvent",
            "IssueCommentEvent",
            "ReleaseEvent",
        ):
            assert f"'{event_type}'" in grid.sql
        assert "`githubarchive.month.202605`" in grid.sql
        assert "$.distinct_size" in grid.sql
        assert "$.size" in grid.sql
        assert "$.pull_request.merged" in grid.sql

    def test_destinations_and_dispositions(self, plan: list[dry_run.QuerySpec]) -> None:
        by_name = {spec.name: spec for spec in plan}
        grid = by_name["extract_events_202605"]
        assert grid.destination == "test-project.codetalent_atlas.events_grid_202605"
        assert grid.skip_if_exists and grid.write_disposition == "WRITE_EMPTY"
        assert by_name["bot_exclusion_audit"].write_disposition == "WRITE_TRUNCATE"
        view = by_name["human_grid_view"]
        assert view.destination is None
        assert "CREATE OR REPLACE VIEW" in view.sql
        quality = by_name["quality_checks"]
        assert quality.destination is None and quality.fetch_rows

    def test_unknown_domain_fails_fast(
        self, config: AtlasConfig, settings: Settings, repo_root: Path
    ) -> None:
        from codetalent.config import ConfigError

        with pytest.raises(ConfigError, match="no taxonomy"):
            dry_run.build_discovery_plan(
                config=config,
                settings=settings,
                domain_id="nope",
                start=date(2026, 5, 1),
                end=date(2026, 7, 31),
                sql_dir=repo_root / "sql",
            )


class TestMonthsInWindow:
    def test_pilot_window(self) -> None:
        assert dry_run.months_in_window(date(2026, 5, 1), date(2026, 7, 31)) == [
            "202605",
            "202606",
            "202607",
        ]

    def test_year_boundary(self) -> None:
        assert dry_run.months_in_window(date(2025, 11, 15), date(2026, 2, 1)) == [
            "202511",
            "202512",
            "202601",
            "202602",
        ]

    def test_inverted_window_fails(self) -> None:
        from codetalent.config import ConfigError

        with pytest.raises(ConfigError):
            dry_run.months_in_window(date(2026, 8, 1), date(2026, 7, 1))
