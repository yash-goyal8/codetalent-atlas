"""Privacy scanner tests (spec section 27): planted violations are caught,
clean aggregates pass, and the repository's real public data dirs are clean."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from codetalent.validation.privacy import (
    DEFAULT_PUBLIC_DIRS,
    PrivacyViolation,
    scan_public_data,
)


def patterns_found(violations: list[PrivacyViolation]) -> set[str]:
    return {v.pattern for v in violations}


class TestPlantedViolations:
    def test_actor_login_and_email_detected(self, tmp_path: Path) -> None:
        planted = tmp_path / "public" / "leaky.json"
        planted.parent.mkdir()
        planted.write_text(
            json.dumps(
                {
                    "actor_login": "octocat",
                    "contact": "octocat@example.com",
                    "score": 91.2,
                }
            ),
            encoding="utf-8",
        )
        violations = scan_public_data((tmp_path / "public",))
        found = patterns_found(violations)
        assert "actor_login field" in found
        assert "email address" in found
        assert all(v.file == planted for v in violations)

    def test_profile_url_user_login_and_token_detected(self, tmp_path: Path) -> None:
        planted = tmp_path / "leak.csv"
        planted.write_text(
            "user_login,profile,raw_location,token\n"
            'octocat,https://github.com/octocat,"Berlin, Germany",'
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n",
            encoding="utf-8",
        )
        found = patterns_found(scan_public_data((tmp_path,)))
        assert "user_login field" in found
        assert "raw_location field" in found
        assert "github profile URL" in found
        assert "API token" in found

    def test_violations_carry_excerpts(self, tmp_path: Path) -> None:
        (tmp_path / "x.json").write_text('{"actor_login": "octocat"}', encoding="utf-8")
        violations = scan_public_data((tmp_path,))
        assert violations
        assert "actor_login" in violations[0].excerpt


class TestCleanData:
    def test_clean_aggregate_file_passes(self, tmp_path: Path, fixtures_dir: Path) -> None:
        shutil.copy(
            fixtures_dir / "public_sample" / "clean_country_rankings.json",
            tmp_path / "countries.json",
        )
        assert scan_public_data((tmp_path,)) == []

    def test_missing_directory_is_not_an_error(self, tmp_path: Path) -> None:
        assert scan_public_data((tmp_path / "does-not-exist",)) == []

    def test_repo_url_is_not_a_profile_url(self, tmp_path: Path) -> None:
        (tmp_path / "meta.json").write_text(
            '{"source": "https://github.com/acme/terraform-widgets"}', encoding="utf-8"
        )
        assert scan_public_data((tmp_path,)) == []


class TestRealPublicDirs:
    def test_current_public_data_dirs_are_clean(self, repo_root: Path) -> None:
        directories = tuple(repo_root / d for d in DEFAULT_PUBLIC_DIRS)
        assert scan_public_data(directories) == []
