"""Response cache keyed by normalized request hash (spec section 14).

Every external response is cached under ``data/cache/github/`` (gitignored) so
runs are deterministic and rerunnable without duplicate API calls.
Target milestone: C.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ResponseCache:
    """Filesystem cache: ``data/cache/github/<kind>/<hash>.json``."""

    def __init__(self, root: Path) -> None:
        raise NotImplementedError("Milestone C implements the response cache.")

    def get(self, request_hash: str) -> dict[str, Any] | None:
        """Return the cached response for a request hash, or None on a miss."""
        raise NotImplementedError("Milestone C implements cache reads.")

    def put(self, request_hash: str, response: dict[str, Any]) -> None:
        """Store one response payload."""
        raise NotImplementedError("Milestone C implements cache writes.")


def request_hash(payload: dict[str, Any]) -> str:
    """Return a stable hash for a normalized request payload."""
    raise NotImplementedError("Milestone C implements request hashing.")
