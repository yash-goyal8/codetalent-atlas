"""GitHub REST client, used only where GraphQL cannot provide a field (spec 5.2, 14).

Minimal authenticated GET with the same safety rules as the GraphQL client:
rate-limit headers are read into a :class:`RateLimitState`, the client pauses
below a configured floor, obeys ``Retry-After`` on 403/429, backs off with
jitter on 5xx, raises immediately on 401, and stops on secondary limits.

Reserved for lightweight raw-content shortlist checks in later milestones; the
Milestone C content-presence signals ride along in the GraphQL batch query.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from codetalent.github.graphql_client import (
    TOKEN_SETUP_INSTRUCTIONS,
    USER_AGENT,
    GitHubAuthenticationError,
    GraphQLRequestError,
    SecondaryRateLimitError,
)
from codetalent.github.rate_limit import (
    RateLimitState,
    compute_backoff_seconds,
    is_secondary_limit,
    parse_rest_rate_limit,
    parse_retry_after,
    seconds_until_reset,
    should_pause,
)

GITHUB_REST_BASE_URL = "https://api.github.com"
DEFAULT_REST_RATE_LIMIT_FLOOR = 50


class RestClient:
    """Authenticated REST client obeying rate-limit headers and Retry-After."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = GITHUB_REST_BASE_URL,
        rate_limit_floor: int = DEFAULT_REST_RATE_LIMIT_FLOOR,
        max_retries: int = 5,
        max_concurrency: int = 2,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not 1 <= max_concurrency <= 2:
            raise ValueError("max_concurrency must be between 1 and 2 (spec section 14)")
        self._rate_limit_floor = rate_limit_floor
        self._max_retries = max_retries
        self.max_concurrency = max_concurrency
        self._sleep = sleep
        self._rng = rng
        self._now = now if now is not None else lambda: datetime.now(UTC)
        self.last_rate_limit: RateLimitState | None = None
        self._client = httpx.Client(
            base_url=base_url,
            transport=transport,
            timeout=timeout,
            headers={
                "Authorization": f"bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": USER_AGENT,
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RestClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """Perform one GET request with rate-limit safety and backoff."""
        state = self.last_rate_limit
        if state is not None and should_pause(state, floor=self._rate_limit_floor):
            self._sleep(seconds_until_reset(state, now=self._now()))
            self.last_rate_limit = None

        attempt = 0
        while True:
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                attempt = self._retry(attempt, f"transport error: {exc}")
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
                attempt = self._retry(attempt, f"HTTP {response.status_code}", delay=retry_after)
                continue

            if response.status_code >= 500:
                attempt = self._retry(attempt, f"HTTP {response.status_code}")
                continue

            parsed = parse_rest_rate_limit(response.headers)
            if parsed is not None:
                self.last_rate_limit = parsed

            if response.status_code >= 400:
                raise GraphQLRequestError(
                    f"REST GET {path} failed with HTTP {response.status_code}", retries=attempt
                )
            return response.json()

    def _retry(self, attempt: int, reason: str, *, delay: float | None = None) -> int:
        if attempt >= self._max_retries:
            raise GraphQLRequestError(
                f"REST request failed after {attempt} retries: {reason}", retries=attempt
            )
        self._sleep(delay if delay is not None else compute_backoff_seconds(attempt, rng=self._rng))
        return attempt + 1
