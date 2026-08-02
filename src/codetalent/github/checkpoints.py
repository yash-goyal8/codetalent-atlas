"""Enrichment checkpointing for resumable runs (spec sections 14, 26).

Persists completed IDs, failed IDs (with retry counts and reasons), the last
observed rate-limit state, and the current adaptive batch size after every
successful batch, so a resumed run never refetches completed records.

Failures whose reason is in :data:`PERMANENT_FAILURE_REASONS` (deleted or
renamed repositories reported as ``NOT_FOUND``) are quarantined permanently and
never retried; transient failures are retried up to the orchestrator's cap.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codetalent.github.rate_limit import RateLimitState

CHECKPOINT_VERSION = 1

#: Failure reasons that will never succeed on retry (fetch-level tombstones).
PERMANENT_FAILURE_REASONS = frozenset({"NOT_FOUND"})


@dataclass(frozen=True)
class FailureRecord:
    """Retry count and latest reason for one failed ID."""

    retries: int
    reason: str


class CheckpointStore:
    """JSON checkpoint file under ``data/interim/checkpoints/`` (atomic writes)."""

    def __init__(self, path: Path, *, default_batch_size: int = 10) -> None:
        self.path = path
        self._completed: set[str] = set()
        self._failed: dict[str, FailureRecord] = {}
        self._last_rate_limit: RateLimitState | None = None
        self._batch_size = default_batch_size
        self._load()

    def _load(self) -> None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        payload = json.loads(raw)
        self._completed = {str(item) for item in payload.get("completed_ids", [])}
        self._failed = {
            str(key): FailureRecord(retries=int(value["retries"]), reason=str(value["reason"]))
            for key, value in payload.get("failed", {}).items()
        }
        rate_limit_raw = payload.get("last_rate_limit")
        self._last_rate_limit = (
            RateLimitState.from_dict(rate_limit_raw) if rate_limit_raw is not None else None
        )
        self._batch_size = int(payload.get("batch_size", self._batch_size))

    def _save(self) -> None:
        payload: dict[str, Any] = {
            "version": CHECKPOINT_VERSION,
            "completed_ids": sorted(self._completed),
            "failed": {
                key: {"retries": record.retries, "reason": record.reason}
                for key, record in sorted(self._failed.items())
            },
            "last_rate_limit": (
                self._last_rate_limit.to_dict() if self._last_rate_limit is not None else None
            ),
            "batch_size": self._batch_size,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)

    def completed_ids(self) -> set[str]:
        """IDs already fetched successfully (copy; mutate via record_batch)."""
        return set(self._completed)

    def failed_records(self) -> dict[str, FailureRecord]:
        """Current failure map (copy; mutate via record_batch)."""
        return dict(self._failed)

    def retriable_failures(self, *, max_retries: int) -> list[str]:
        """Failed IDs eligible for another attempt, sorted for determinism."""
        return sorted(
            key
            for key, record in self._failed.items()
            if record.retries < max_retries and record.reason not in PERMANENT_FAILURE_REASONS
        )

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def last_rate_limit(self) -> RateLimitState | None:
        return self._last_rate_limit

    def record_batch(
        self,
        completed: Iterable[str],
        failed: Mapping[str, str],
        *,
        rate_limit: RateLimitState | None = None,
        batch_size: int | None = None,
    ) -> None:
        """Persist the outcome of one batch atomically.

        ``failed`` maps ID -> reason; each entry increments the ID's retry
        count. IDs that later succeed are removed from the failure map.
        """
        for repo_id in completed:
            self._completed.add(repo_id)
            self._failed.pop(repo_id, None)
        for repo_id, reason in failed.items():
            previous = self._failed.get(repo_id)
            retries = previous.retries + 1 if previous is not None else 1
            self._failed[repo_id] = FailureRecord(retries=retries, reason=reason)
        if rate_limit is not None:
            self._last_rate_limit = rate_limit
        if batch_size is not None:
            self._batch_size = batch_size
        self._save()
