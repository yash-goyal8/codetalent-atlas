"""Data-quality checks over pipeline tables (spec sections 18, 28).

Nulls, duplicates, referential integrity, schema compliance, date bounds,
score bounds, and aggregate totals, each with the failure behavior from the
spec's test matrix. Target milestone: E.
"""

from __future__ import annotations

from pathlib import Path


def check_dataset(processed_dir: Path) -> list[str]:
    """Run all data-quality checks and return human-readable failure messages."""
    raise NotImplementedError("Milestone E implements data-quality checks.")
