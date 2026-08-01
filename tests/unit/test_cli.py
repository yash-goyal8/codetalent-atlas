"""CLI surface tests: help output, stub exit codes, and the real local stages."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from codetalent.cli import app

runner = CliRunner()

GROUPS = ["bq", "github", "classify", "locations", "score", "validate", "publish", "pipeline"]

STUB_COMMANDS: list[tuple[list[str], str]] = [
    (["bq", "dry-run"], "Milestone B"),
    (["bq", "discover"], "Milestone B"),
    (["github", "enrich-repos"], "Milestone C"),
    (["classify", "repos"], "Milestone C"),
    (["github", "enrich-users"], "Milestone D"),
    (["locations", "normalize"], "Milestone D"),
    (["score", "repositories"], "Milestone E"),
    (["score", "contributors"], "Milestone E"),
    (["score", "geographies"], "Milestone E"),
    (["publish", "web-data"], "Milestone F"),
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

    @pytest.mark.parametrize(("args", "_milestone"), STUB_COMMANDS)
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
        assert "Milestone B" in result.output

    def test_invalid_config_stops_pipeline(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["pipeline", "pilot", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "[fail] configuration invalid" in result.output
