"""Build-time JSON compression for hosting budgets (spec 5.6, Phase 10 performance).

Keeps every deployed asset under the 25 MiB per-file limit and payload
targets (country rankings < 1 MiB, city details < 250 KiB).
Target milestone: F.
"""

from __future__ import annotations

from pathlib import Path


def compress_assets(data_dir: Path) -> list[Path]:
    """Compress large JSON assets in place and return the files written."""
    raise NotImplementedError("Milestone F implements asset compression.")
