"""Structured JSON-lines run logging (spec section 26).

Every pipeline step emits exactly one JSON object per line containing the
fields required by the specification. Lines go to stderr by default so stdout
stays clean for command output; pass ``stream`` to write to a log file instead.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

LOG_FIELDS: tuple[str, ...] = (
    "run_id",
    "phase",
    "step",
    "status",
    "records_in",
    "records_out",
    "cache_hits",
    "api_cost",
    "bytes_processed",
    "duration_seconds",
    "error_type",
)


def new_run_id() -> str:
    """Return a fresh identifier for one pipeline run."""
    return uuid.uuid4().hex[:12]


def log_step(
    *,
    run_id: str,
    phase: str,
    step: str,
    status: str,
    records_in: int | None = None,
    records_out: int | None = None,
    cache_hits: int | None = None,
    api_cost: float | None = None,
    bytes_processed: int | None = None,
    duration_seconds: float | None = None,
    error_type: str | None = None,
    stream: TextIO | None = None,
) -> dict[str, object]:
    """Emit one structured log line and return the emitted record."""
    record: dict[str, object] = {
        "run_id": run_id,
        "phase": phase,
        "step": step,
        "status": status,
        "records_in": records_in,
        "records_out": records_out,
        "cache_hits": cache_hits,
        "api_cost": api_cost,
        "bytes_processed": bytes_processed,
        "duration_seconds": duration_seconds,
        "error_type": error_type,
    }
    out = stream if stream is not None else sys.stderr
    out.write(json.dumps(record, separators=(",", ":")) + "\n")
    out.flush()
    return record


class RunLogger:
    """Convenience wrapper binding ``run_id``/``phase`` for a sequence of steps."""

    def __init__(self, phase: str, *, run_id: str | None = None, stream: TextIO | None = None):
        self.run_id = run_id if run_id is not None else new_run_id()
        self.phase = phase
        self.stream = stream

    def step(self, step: str, status: str, **fields: int | float | str | None) -> dict[str, object]:
        """Emit one step record within this run."""
        return log_step(
            run_id=self.run_id,
            phase=self.phase,
            step=step,
            status=status,
            stream=self.stream,
            **fields,  # type: ignore[arg-type]
        )

    @contextmanager
    def timed(self, step: str) -> Iterator[None]:
        """Log ``started``, then ``completed`` (or ``failed``) with wall duration."""
        start = time.monotonic()
        self.step(step, "started")
        try:
            yield
        except Exception as exc:
            self.step(
                step,
                "failed",
                duration_seconds=round(time.monotonic() - start, 3),
                error_type=type(exc).__name__,
            )
            raise
        self.step(step, "completed", duration_seconds=round(time.monotonic() - start, 3))
