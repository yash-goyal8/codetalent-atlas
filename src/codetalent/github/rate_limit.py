"""Rate-limit state machine and backoff policy (spec section 14).

Implements the non-negotiable API-safety behaviors shared by the GraphQL and
REST clients:

* parse the GraphQL ``rateLimit`` block and REST ``x-ratelimit-*`` headers into
  one :class:`RateLimitState`;
* pause before the remaining budget crosses a configured floor
  (:func:`should_pause` + :func:`seconds_until_reset`, default floor 200);
* honor ``Retry-After`` on 403/429 (:func:`parse_retry_after`);
* exponential backoff with jitter (:func:`compute_backoff_seconds`);
* detect secondary rate limits (:func:`is_secondary_limit`), which callers must
  treat as stop-and-preserve-checkpoint.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

GRAPHQL_RESOURCE = "graphql"
REST_RESOURCE = "core"

DEFAULT_RATE_LIMIT_FLOOR = 200
#: Extra seconds slept past the reported reset time, absorbing clock skew.
RESET_SLEEP_BUFFER_SECONDS = 2.0

_SECONDARY_LIMIT_SNIPPET = "secondary rate limit"

_module_rng = random.Random()


@dataclass(frozen=True)
class RateLimitState:
    """Last observed rate-limit budget for one resource type."""

    resource: str
    remaining: int
    reset_at: datetime | None
    limit: int | None = None
    last_cost: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable form for checkpoint persistence."""
        return {
            "resource": self.resource,
            "remaining": self.remaining,
            "reset_at": self.reset_at.isoformat() if self.reset_at is not None else None,
            "limit": self.limit,
            "last_cost": self.last_cost,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RateLimitState:
        """Inverse of :meth:`to_dict`."""
        reset_raw = payload.get("reset_at")
        limit = payload.get("limit")
        last_cost = payload.get("last_cost")
        return cls(
            resource=str(payload["resource"]),
            remaining=int(payload["remaining"]),
            reset_at=_parse_iso(reset_raw) if isinstance(reset_raw, str) else None,
            limit=int(limit) if limit is not None else None,
            last_cost=int(last_cost) if last_cost is not None else None,
        )


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def parse_graphql_rate_limit(data: Mapping[str, Any] | None) -> RateLimitState | None:
    """Read the ``rateLimit`` block of a GraphQL ``data`` payload, if present."""
    block = (data or {}).get("rateLimit")
    if not isinstance(block, Mapping):
        return None
    reset_raw = block.get("resetAt")
    limit = block.get("limit")
    cost = block.get("cost")
    return RateLimitState(
        resource=GRAPHQL_RESOURCE,
        remaining=int(block.get("remaining", 0)),
        reset_at=_parse_iso(reset_raw) if isinstance(reset_raw, str) else None,
        limit=int(limit) if limit is not None else None,
        last_cost=int(cost) if cost is not None else None,
    )


def parse_rest_rate_limit(headers: Mapping[str, str]) -> RateLimitState | None:
    """Read ``x-ratelimit-*`` response headers (httpx headers are lower-cased)."""
    remaining_raw = headers.get("x-ratelimit-remaining")
    if remaining_raw is None or not remaining_raw.isdigit():
        return None
    reset_raw = headers.get("x-ratelimit-reset")
    reset_at = (
        datetime.fromtimestamp(int(reset_raw), tz=UTC)
        if reset_raw is not None and reset_raw.isdigit()
        else None
    )
    limit_raw = headers.get("x-ratelimit-limit")
    return RateLimitState(
        resource=headers.get("x-ratelimit-resource", REST_RESOURCE),
        remaining=int(remaining_raw),
        reset_at=reset_at,
        limit=int(limit_raw) if limit_raw is not None and limit_raw.isdigit() else None,
    )


def should_pause(state: RateLimitState, *, floor: int = DEFAULT_RATE_LIMIT_FLOOR) -> bool:
    """True when the remaining budget has dropped below the configured floor."""
    return state.remaining < floor


def seconds_until_reset(state: RateLimitState, *, now: datetime | None = None) -> float:
    """Seconds to sleep until the budget resets (plus a small skew buffer)."""
    if state.reset_at is None:
        return RESET_SLEEP_BUFFER_SECONDS
    current = now if now is not None else datetime.now(UTC)
    return max(0.0, (state.reset_at - current).total_seconds()) + RESET_SLEEP_BUFFER_SECONDS


def compute_backoff_seconds(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = 120.0,
    rng: random.Random | None = None,
) -> float:
    """Exponential backoff with jitter: ``min(cap, base * 2**attempt) * U(0.5, 1.0)``.

    ``attempt`` is 0-based (the first retry passes 0). The jitter factor keeps at
    least half of the exponential delay so retries never collapse to zero.
    """
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    delay = min(cap, base * (2.0**attempt))
    jitter = (rng if rng is not None else _module_rng).uniform(0.5, 1.0)
    return delay * jitter


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header holding integer seconds; None otherwise."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped.isdigit():
        return None
    return float(stripped)


def is_secondary_limit(text: str) -> bool:
    """True when an error body or GraphQL message names a secondary rate limit."""
    return _SECONDARY_LIMIT_SNIPPET in text.lower()
