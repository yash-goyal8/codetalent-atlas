"""Batched GitHub GraphQL client (spec section 14).

Synchronous httpx client enforcing the non-negotiable API-safety rules:

1. Every response's ``rateLimit`` block is read; before the next request, when
   the remaining budget is below the configured floor (default 200), the client
   sleeps until ``resetAt``.
2. ``Retry-After`` is obeyed on 403/429; transient failures use exponential
   backoff with jitter; secondary-limit errors raise
   :class:`SecondaryRateLimitError` immediately so the caller can stop and
   preserve its checkpoint.
3. Requests are issued strictly sequentially (one in flight), and the
   configurable ``max_concurrency`` is validated to never exceed the spec's
   conservative cap of 2.
4. HTTP 401 raises :class:`GitHubAuthenticationError` immediately, carrying
   token setup instructions — never retried.

Partial per-alias errors (e.g. one deleted repository inside a batch) are NOT
exceptions: when the response carries ``data``, the result exposes both the
data and the error list so the caller can quarantine individual records.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from codetalent.github.rate_limit import (
    DEFAULT_RATE_LIMIT_FLOOR,
    RateLimitState,
    compute_backoff_seconds,
    is_secondary_limit,
    parse_graphql_rate_limit,
    parse_retry_after,
    seconds_until_reset,
    should_pause,
)

GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
USER_AGENT = "codetalent-atlas/0.1"
MAX_CONCURRENCY_CAP = 2

TOKEN_SETUP_INSTRUCTIONS = (
    "GitHub rejected the credentials. Set up a token:\n"
    "  1. Create a fine-grained personal access token at "
    "https://github.com/settings/tokens with read-only access to public "
    "repositories only (no additional scopes or permissions).\n"
    "  2. Add GITHUB_TOKEN=<token> to the gitignored .env file at the repository root.\n"
    "  3. Re-run the command."
)


class GitHubAuthenticationError(RuntimeError):
    """HTTP 401 — fail immediately with setup instructions (spec section 26)."""


class SecondaryRateLimitError(RuntimeError):
    """GitHub reported a secondary rate limit — stop and preserve the checkpoint."""


class GraphQLRequestError(RuntimeError):
    """A GraphQL request failed after retries, or returned no usable data."""

    def __init__(self, message: str, *, retries: int = 0) -> None:
        super().__init__(message)
        self.retries = retries


@dataclass(frozen=True)
class GraphQLResult:
    """One successful GraphQL exchange (possibly with partial per-alias errors)."""

    data: dict[str, Any]
    errors: list[dict[str, Any]]
    rate_limit: RateLimitState | None
    response_bytes: int
    retries: int


class GraphQLClient:
    """Authenticated GraphQL client honoring the spec's rate-limit behavior rules."""

    def __init__(
        self,
        token: str,
        *,
        endpoint: str = GITHUB_GRAPHQL_ENDPOINT,
        rate_limit_floor: int = DEFAULT_RATE_LIMIT_FLOOR,
        max_retries: int = 5,
        max_concurrency: int = 2,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= max_concurrency <= MAX_CONCURRENCY_CAP:
            raise ValueError(
                f"max_concurrency must be between 1 and {MAX_CONCURRENCY_CAP} (spec section 14)"
            )
        self._endpoint = endpoint
        self._rate_limit_floor = rate_limit_floor
        self._max_retries = max_retries
        # The synchronous client issues at most one request at a time, which is
        # always within the configured (<= 2) concurrency bound.
        self.max_concurrency = max_concurrency
        self._sleep = sleep
        self._rng = rng
        self._now = now if now is not None else lambda: datetime.now(UTC)
        self.last_rate_limit: RateLimitState | None = None
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers={
                "Authorization": f"bearer {token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GraphQLClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- internals -----------------------------------------------------------

    def _pause_if_needed(self) -> None:
        state = self.last_rate_limit
        if state is not None and should_pause(state, floor=self._rate_limit_floor):
            self._sleep(seconds_until_reset(state, now=self._now()))
            # The budget has reset; drop the stale state so we do not re-sleep.
            self.last_rate_limit = None

    def _backoff_retry(self, attempt: int, reason: str, *, delay: float | None = None) -> int:
        """Sleep and return the next attempt number, or raise when exhausted."""
        if attempt >= self._max_retries:
            raise GraphQLRequestError(
                f"GraphQL request failed after {attempt} retries: {reason}", retries=attempt
            )
        self._sleep(delay if delay is not None else compute_backoff_seconds(attempt, rng=self._rng))
        return attempt + 1

    # -- API -----------------------------------------------------------------

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> GraphQLResult:
        """Execute one GraphQL request, reading rateLimit data from the response."""
        self._pause_if_needed()
        body: dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables

        attempt = 0
        while True:
            try:
                response = self._client.post(self._endpoint, json=body)
            except httpx.TransportError as exc:
                attempt = self._backoff_retry(attempt, f"transport error: {exc}")
                continue

            if response.status_code == 401:
                raise GitHubAuthenticationError(TOKEN_SETUP_INSTRUCTIONS)

            if response.status_code in (403, 429):
                if is_secondary_limit(response.text):
                    raise SecondaryRateLimitError(
                        "GitHub reported a secondary rate limit; stopping to preserve "
                        "the checkpoint. Re-run later to resume."
                    )
                retry_after = parse_retry_after(response.headers.get("retry-after"))
                attempt = self._backoff_retry(
                    attempt, f"HTTP {response.status_code}", delay=retry_after
                )
                continue

            if response.status_code >= 500:
                attempt = self._backoff_retry(attempt, f"HTTP {response.status_code}")
                continue

            if response.status_code != 200:
                raise GraphQLRequestError(
                    f"unexpected HTTP {response.status_code}: {response.text[:200]}",
                    retries=attempt,
                )

            # A proxy/CDN can mangle a 200 into a non-JSON (or non-object)
            # body; treat it like any other transient failure so it is retried
            # and, when persistent, surfaces as GraphQLRequestError — which the
            # orchestrator ledgers and quarantines per batch (spec rules 5, 6).
            try:
                payload = response.json()
            except (json.JSONDecodeError, ValueError) as exc:
                attempt = self._backoff_retry(attempt, f"malformed JSON body: {exc}")
                continue
            if not isinstance(payload, dict):
                attempt = self._backoff_retry(
                    attempt, f"non-object JSON body: {type(payload).__name__}"
                )
                continue
            errors = [error for error in payload.get("errors") or [] if isinstance(error, dict)]
            for error in errors:
                if is_secondary_limit(str(error.get("message", ""))):
                    raise SecondaryRateLimitError(
                        "GitHub reported a secondary rate limit in the GraphQL error "
                        "list; stopping to preserve the checkpoint."
                    )
            data = payload.get("data")
            if not isinstance(data, dict):
                messages = "; ".join(str(error.get("message", "")) for error in errors)
                raise GraphQLRequestError(
                    f"GraphQL request returned no data: {messages[:300]}", retries=attempt
                )

            state = parse_graphql_rate_limit(data)
            if state is not None:
                self.last_rate_limit = state
            return GraphQLResult(
                data=data,
                errors=errors,
                rate_limit=state,
                response_bytes=len(response.content),
                retries=attempt,
            )
