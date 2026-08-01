"""Dataset manifest generation (spec Phase 10 manifest contract, section 22 versioning).

Writes ``web/public/data/manifest.json`` with dataset version
(``YYYY.MM.DD-<scope>.<revision>``), window, domains, file map, and
methodology version. Target milestone: F.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path


def build_manifest(
    output_path: Path,
    *,
    dataset_version: str,
    window_start: date,
    window_end: date,
    domains: list[str],
    methodology_version: str,
) -> Path:
    """Write the manifest JSON and return its path."""
    raise NotImplementedError("Milestone F implements manifest generation.")
