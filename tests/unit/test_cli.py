"""CLI surface tests: help output, stub exit codes, and the real local stages."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from codetalent.cli import app
from codetalent.github.enrich_repos import EnrichmentReport
from codetalent.settings import Settings

runner = CliRunner()

GROUPS = ["bq", "github", "classify", "locations", "score", "validate", "publish", "pipeline"]

STUB_COMMANDS: list[tuple[list[str], str]] = [
    (["score", "repositories"], "Milestone E"),
    (["score", "contributors"], "Milestone E"),
    (["score", "geographies"], "Milestone E"),
    (["publish", "web-data"], "Milestone F"),
]

IMPLEMENTED_MILESTONE_C_COMMANDS: list[list[str]] = [
    ["github", "enrich-repos"],
    ["classify", "repos"],
]


class TestHelp:
    def test_app_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in GROUPS:
            assert group in result.output

    @pytest.mark.parametrize("group", GROUPS)
    def test_group_help(self, group: str) -> None:
        result = runner.invoke(app, [group, "--help"])
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("args", "_milestone"),
        STUB_COMMANDS + [(args, "C") for args in IMPLEMENTED_MILESTONE_C_COMMANDS],
    )
    def test_command_help(self, args: list[str], _milestone: str) -> None:
        result = runner.invoke(app, [*args, "--help"])
        assert result.exit_code == 0


class TestStubs:
    @pytest.mark.parametrize(("args", "milestone"), STUB_COMMANDS)
    def test_stub_exits_2_and_names_milestone(self, args: list[str], milestone: str) -> None:
        result = runner.invoke(app, args)
        assert result.exit_code == 2
        assert "not implemented yet" in result.output
        assert milestone in result.output


def _settings_with_token(token: str | None) -> Settings:
    return Settings(github_token=SecretStr(token) if token is not None else None, _env_file=None)


class TestGithubEnrichRepos:
    def test_missing_token_fails_with_instructions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("codetalent.cli.load_settings", lambda: _settings_with_token(None))
        result = runner.invoke(app, ["github", "enrich-repos"])
        assert result.exit_code == 1
        assert "GITHUB_TOKEN" in result.output

    def test_runs_orchestrator_and_echoes_summary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("codetalent.cli.load_settings", lambda: _settings_with_token("t"))
        captured: dict[str, object] = {}

        def fake_enrich(**kwargs: object) -> EnrichmentReport:
            captured.update(kwargs)
            return EnrichmentReport(
                worklist_total=15,
                already_completed=5,
                attempted=10,
                succeeded=9,
                failed=1,
                cache_hits=2,
                batch_size=25,
                total_rows=14,
                output_path=Path("data/interim/repository_metadata.parquet"),
                exhausted_failures={"owner00/repo00": "REQUEST_ERROR:GraphQLRequestError"},
            )

        monkeypatch.setattr("codetalent.github.enrich_repos.enrich_repositories", fake_enrich)
        result = runner.invoke(app, ["github", "enrich-repos", "--limit", "10"])
        assert result.exit_code == 0
        assert captured["limit"] == 10
        assert captured["max_failure_retries"] == 3
        assert captured["input_path"] == Path("data/interim/repository_activity_summary.parquet")
        assert "15 accepted repositories" in result.output
        assert "9 enriched" in result.output
        assert "repository_metadata.parquet" in result.output
        # Exhausted-retry records are surfaced with their reasons.
        assert "exhausted their retry budget" in result.output
        assert "owner00/repo00: REQUEST_ERROR:GraphQLRequestError" in result.output
        assert "--max-failure-retries" in result.output

    def test_missing_worklist_fails_cleanly(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("codetalent.cli.load_settings", lambda: _settings_with_token("t"))
        result = runner.invoke(
            app, ["github", "enrich-repos", "--input", str(tmp_path / "missing.parquet")]
        )
        assert result.exit_code == 1
        assert "worklist not found" in result.output


class TestClassifyRepos:
    def test_calls_runner_contract_and_echoes_counts(
        self, monkeypatch: pytest.MonkeyPatch, config_dir: Path
    ) -> None:
        captured: dict[str, object] = {}
        module = types.ModuleType("codetalent.classify.runner")

        def fake_classify(**kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                total=10,
                accepted=4,
                rejected=5,
                borderline=1,
                output_path=Path("data/interim/repository_classification.parquet"),
            )

        module.classify_repositories = fake_classify  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "codetalent.classify.runner", module)

        result = runner.invoke(
            app, ["classify", "repos", "--domain", "cloud_devops", "--config-dir", str(config_dir)]
        )
        assert result.exit_code == 0
        assert captured["domain_id"] == "cloud_devops"
        assert captured["metadata_path"] == Path("data/interim/repository_metadata.parquet")
        assert captured["activity_path"] == Path("data/interim/repository_activity_summary.parquet")
        assert "4 accepted, 5 rejected, 1 borderline" in result.output

    def test_unknown_domain_fails(self, config_dir: Path) -> None:
        result = runner.invoke(
            app, ["classify", "repos", "--domain", "nope", "--config-dir", str(config_dir)]
        )
        assert result.exit_code == 1
        assert "no taxonomy configured" in result.output


class TestVersion:
    def test_version_command(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert result.output.strip() == "0.1.0"


class TestValidateAll:
    def test_runs_real_stages_and_reports_pending(self, config_dir: Path) -> None:
        result = runner.invoke(app, ["validate", "all", "--config-dir", str(config_dir)])
        assert result.exit_code == 0
        assert "[ok] configuration valid" in result.output
        assert "privacy scan" in result.output
        assert "[pending]" in result.output
        assert "all available stages passed" in result.output

    def test_invalid_config_fails_with_exit_1(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["validate", "all", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "[fail] configuration invalid" in result.output


class TestPipelinePilot:
    def test_lists_stages_runs_config_validation_then_stops(self, config_dir: Path) -> None:
        result = runner.invoke(app, ["pipeline", "pilot", "--config-dir", str(config_dir)])
        assert result.exit_code == 2
        assert "Pilot pipeline stages:" in result.output
        assert "config-validation" in result.output
        assert "[ok] configuration valid" in result.output
        assert "stopped before stage 'bq-discover'" in result.output
        assert "codetalent bq dry-run" in result.output

    def test_invalid_config_stops_pipeline(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["pipeline", "pilot", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "[fail] configuration invalid" in result.output
