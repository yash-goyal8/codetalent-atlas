"""Rate-limit state machine tests: floor, reset sleep, backoff, Retry-After."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from codetalent.github.rate_limit import (
    RESET_SLEEP_BUFFER_SECONDS,
    RateLimitState,
    compute_backoff_seconds,
    is_secondary_limit,
    parse_graphql_rate_limit,
    parse_rest_rate_limit,
    parse_retry_after,
    seconds_until_reset,
    should_pause,
)

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)


class TestParseGraphQL:
    def test_reads_all_fields(self) -> None:
        state = parse_graphql_rate_limit(
            {
                "rateLimit": {
                    "limit": 5000,
                    "cost": 3,
                    "remaining": 4321,
                    "resetAt": "2026-08-02T13:00:00Z",
                }
            }
        )
        assert state is not None
        assert state.remaining == 4321
        assert state.limit == 5000
        assert state.last_cost == 3
        assert state.reset_at == datetime(2026, 8, 2, 13, 0, 0, tzinfo=UTC)

    def test_missing_block_returns_none(self) -> None:
        assert parse_graphql_rate_limit({}) is None
        assert parse_graphql_rate_limit(None) is None


class TestParseRest:
    def test_reads_headers(self) -> None:
        state = parse_rest_rate_limit(
            {
                "x-ratelimit-remaining": "42",
                "x-ratelimit-reset": str(int(NOW.timestamp())),
                "x-ratelimit-limit": "5000",
            }
        )
        assert state is not None
        assert state.remaining == 42
        assert state.limit == 5000
        assert state.reset_at == NOW

    def test_missing_headers_return_none(self) -> None:
        assert parse_rest_rate_limit({}) is None


class TestShouldPause:
    def test_below_floor_pauses(self) -> None:
        state = RateLimitState("graphql", remaining=199, reset_at=NOW)
        assert should_pause(state, floor=200)

    def test_at_floor_does_not_pause(self) -> None:
        state = RateLimitState("graphql", remaining=200, reset_at=NOW)
        assert not should_pause(state, floor=200)


class TestSecondsUntilReset:
    def test_future_reset_sleeps_until_reset_plus_buffer(self) -> None:
        state = RateLimitState(
            "graphql", remaining=0, reset_at=datetime(2026, 8, 2, 12, 10, 0, tzinfo=UTC)
        )
        assert seconds_until_reset(state, now=NOW) == 600.0 + RESET_SLEEP_BUFFER_SECONDS

    def test_past_reset_sleeps_only_the_buffer(self) -> None:
        state = RateLimitState(
            "graphql", remaining=0, reset_at=datetime(2026, 8, 2, 11, 0, 0, tzinfo=UTC)
        )
        assert seconds_until_reset(state, now=NOW) == RESET_SLEEP_BUFFER_SECONDS

    def test_unknown_reset_sleeps_only_the_buffer(self) -> None:
        state = RateLimitState("graphql", remaining=0, reset_at=None)
        assert seconds_until_reset(state, now=NOW) == RESET_SLEEP_BUFFER_SECONDS


class TestComputeBackoff:
    def test_grows_exponentially_within_jitter_bounds(self) -> None:
        rng = random.Random(7)
        for attempt in range(5):
            expected_max = min(120.0, 2.0**attempt)
            delay = compute_backoff_seconds(attempt, rng=rng)
            assert expected_max / 2 <= delay <= expected_max

    def test_capped(self) -> None:
        delay = compute_backoff_seconds(30, cap=120.0, rng=random.Random(1))
        assert delay <= 120.0

    def test_negative_attempt_rejected(self) -> None:
        with pytest.raises(ValueError, match="attempt"):
            compute_backoff_seconds(-1)


class TestRetryAfter:
    def test_integer_seconds(self) -> None:
        assert parse_retry_after("30") == 30.0
        assert parse_retry_after(" 5 ") == 5.0

    def test_missing_or_unparseable(self) -> None:
        assert parse_retry_after(None) is None
        assert parse_retry_after("") is None
        assert parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None


class TestSecondaryLimitDetection:
    def test_detects_case_insensitively(self) -> None:
        assert is_secondary_limit("You have exceeded a Secondary Rate Limit.")
        assert not is_secondary_limit("API rate limit exceeded for user ID 1.")


class TestStateSerialization:
    def test_round_trip(self) -> None:
        state = RateLimitState("graphql", remaining=100, reset_at=NOW, limit=5000, last_cost=2)
        assert RateLimitState.from_dict(state.to_dict()) == state

    def test_round_trip_with_nulls(self) -> None:
        state = RateLimitState("core", remaining=1, reset_at=None)
        assert RateLimitState.from_dict(state.to_dict()) == state
