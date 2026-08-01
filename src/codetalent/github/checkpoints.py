"""Enrichment checkpointing for resumable runs (spec sections 14, 26).

Persists completed IDs, failed IDs, retry counts, last rate-limit state, and
current batch size after every successful batch, so a resumed run never
refetches completed records. Target milestone: C.
"""

from __future__ import annotations

from pathlib import Path


class CheckpointStore:
    """JSON checkpoint file under ``data/interim/checkpoints/``."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("Milestone C implements checkpoint persistence.")

    def completed_ids(self) -> set[str]:
        """Return IDs already fetched successfully."""
        raise NotImplementedError("Milestone C implements checkpoint reads.")

    def record_batch(self, completed: list[str], failed: list[str]) -> None:
        """Persist the outcome of one batch atomically."""
        raise NotImplementedError("Milestone C implements checkpoint writes.")
