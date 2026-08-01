"""Rate-limit tracking and backoff policy (spec section 14).

Reads GraphQL ``rateLimit`` data and REST rate-limit headers, pauses before
budgets are exhausted, obeys Retry-After, and applies exponential backoff with
jitter. Target milestone: C.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitState:
    """Last observed rate-limit budget for one resource type."""

    resource: str
    remaining: int
    reset_at_epoch: float


def compute_backoff_seconds(attempt: int, *, base: float = 1.0, cap: float = 120.0) -> float:
    """Return the exponential-backoff-with-jitter delay for a retry attempt."""
    raise NotImplementedError("Milestone C implements backoff computation.")


def should_pause(state: RateLimitState, *, reserve: int = 100) -> bool:
    """Return True when the remaining budget is close enough to exhaustion to pause."""
    raise NotImplementedError("Milestone C implements pause decisions.")
