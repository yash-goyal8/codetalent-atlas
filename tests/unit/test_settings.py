"""Settings tests: defaults, environment overrides, and secret masking."""

from __future__ import annotations

from pathlib import Path

import pytest

from codetalent.settings import Settings

ENV_VARS = [
    "GITHUB_TOKEN",
    "GOOGLE_CLOUD_PROJECT",
    "BIGQUERY_LOCATION",
    "BIGQUERY_MAX_BYTES_PHASE3",
    "DATASET_ID",
    "CACHE_DIR",
    "LOG_LEVEL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def make_settings(**kwargs: object) -> Settings:
    """Build Settings without reading any local .env file."""
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


class TestDefaults:
    def test_defaults_match_spec_section_25(self) -> None:
        settings = make_settings()
        assert settings.github_token is None
        assert settings.google_cloud_project is None
        assert settings.bigquery_location == "US"
        assert settings.bigquery_max_bytes_phase3 == 268_435_456_000
        assert settings.dataset_id == "codetalent_atlas"
        assert settings.cache_dir == Path("data/cache")
        assert settings.log_level == "INFO"


class TestEnvOverrides:
    def test_env_values_override_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATASET_ID", "atlas_test")
        monkeypatch.setenv("BIGQUERY_LOCATION", "EU")
        monkeypatch.setenv("BIGQUERY_MAX_BYTES_PHASE3", "1000")
        monkeypatch.setenv("CACHE_DIR", "/tmp/atlas-cache")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        settings = make_settings()
        assert settings.dataset_id == "atlas_test"
        assert settings.bigquery_location == "EU"
        assert settings.bigquery_max_bytes_phase3 == 1000
        assert settings.cache_dir == Path("/tmp/atlas-cache")
        assert settings.log_level == "DEBUG"

    def test_github_token_read_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "dummy-token-value")
        settings = make_settings()
        assert settings.github_token is not None
        assert settings.github_token.get_secret_value() == "dummy-token-value"


class TestSecretMasking:
    def test_token_never_appears_in_repr_or_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "super-secret-value")
        settings = make_settings()
        for rendered in (repr(settings), str(settings), repr(settings.github_token)):
            assert "super-secret-value" not in rendered

    def test_model_dump_masks_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "super-secret-value")
        dumped = str(make_settings().model_dump())
        assert "super-secret-value" not in dumped
