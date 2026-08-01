"""Export BigQuery results to local Parquet before sandbox tables expire.

Sandbox tables have a limited lifetime, so every permanent result is
materialized to ``data/interim`` as Parquet. Target milestone: B.
"""

from __future__ import annotations

from pathlib import Path


def export_table_to_parquet(table_id: str, destination: Path, *, project: str) -> Path:
    """Download one result table to a local Parquet file and return its path."""
    raise NotImplementedError("Milestone B implements local Parquet export.")
