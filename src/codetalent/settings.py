"""Runtime settings loaded from the environment (spec section 25).

Settings are read from process environment variables and, when present, a local
``.env`` file. ``GITHUB_TOKEN`` is held as a :class:`pydantic.SecretStr` so it is
masked in ``repr``/``str`` output and never appears in logs; call
``settings.github_token.get_secret_value()`` only at the API-client boundary.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration matching ``.env.example``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: SecretStr | None = None
    google_cloud_project: str | None = None
    bigquery_location: str = "US"
    bigquery_max_bytes_phase3: int = 268_435_456_000
    dataset_id: str = "codetalent_atlas"
    cache_dir: Path = Path("data/cache")
    log_level: str = "INFO"


def load_settings() -> Settings:
    """Load settings from the environment and an optional ``.env`` file."""
    return Settings()
