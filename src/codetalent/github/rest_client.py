"""GitHub REST client, used only where GraphQL cannot provide a field (spec 5.2, 14).

Covers lightweight raw-content existence checks (README, CONTRIBUTING,
CODE_OF_CONDUCT, CI config, test signals) for a small shortlist only.
Target milestone: C.
"""

from __future__ import annotations

from typing import Any


class RestClient:
    """Authenticated REST client obeying rate-limit headers and Retry-After."""

    def __init__(self, token: str, *, max_concurrency: int = 2) -> None:
        raise NotImplementedError("Milestone C implements the REST client.")

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """Perform one GET request with caching and backoff."""
        raise NotImplementedError("Milestone C implements REST requests.")
