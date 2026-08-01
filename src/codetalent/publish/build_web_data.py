"""Static web dataset builder (spec Phase 10 data contract).

Generates the aggregate-only JSON files under ``web/public/data/`` (manifest,
summary, rankings, location details, methodology, recommendations). The
privacy scanner must pass on the output before deployment. Target milestone: F.
"""

from __future__ import annotations

from pathlib import Path


def build_web_data(processed_dir: Path, output_dir: Path, *, dataset_version: str) -> Path:
    """Build all public JSON assets and return the output directory."""
    raise NotImplementedError("Milestone F implements the static data builder.")
