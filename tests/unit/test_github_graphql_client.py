"""GraphQL client tests: rate-limit floor, Retry-After, backoff, secondary limits."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import httpx
import pytest
from _github_fakes import (
    ScriptedHandler,
    SleepRecorder,
    graphql_success_response,
    repo_node,
)

from codetalent.github.graphql_client import (
    GitHubAuthenticationError,
    GraphQLClient,
    GraphQLRequestError,
    SecondaryRateLimitError,
)
from codetalent.github.rate_limit import RESET_SLEEP_BUFFER_SECONDS

QUERY = "query { rateLimit { limit cost remaining resetAt } }"
NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)


def make_client(
    handler: ScriptedHandler,
    *,
    sleep: SleepRecorder | None = None,
    max_retries: int = 3,
    rate_limit_floor: int = 200,
) -> GraphQLClient:
    return GraphQLClient(
        "test-token",
        transport=httpx.MockTransport(handler),
        sleep=sleep if sleep is not None else SleepRecorder(),
        rng=random.Random(7),
        now=lambda: NOW,
        max_retries=max_retries,
        rate_limit_floor=rate_limit_floor,
    )


class TestSuccess:
    def test_returns_data_and_rate_limit_state(self) -> None:
        handler = ScriptedHandler(
            [graphql_success_response({"r0": repo_node("a/one")}, cost=1, remaining=4990)]
        )
        with make_client(handler) as client:
            result = client.execute(QUERY)
        assert result.data["r0"]["nameWithOwner"] == "a/one"
        assert result.errors == []
        assert result.retries == 0
        assert result.rate_limit is not None
        assert result.rate_limit.remaining == 4990
        assert result.rate_limit.last_cost == 1
        assert client.last_rate_limit == result.rate_limit
        assert result.response_bytes > 0

    def test_sends_bearer_auth_to_graphql_endpoint(self) -> None:
        handler = ScriptedHandler([graphql_success_response({})])
        with make_client(handler) as client:
            client.execute(QUERY)
        request = handler.requests[0]
        assert str(request.url) == "https://api.github.com/graphql"
        assert request.headers["authorization"] == "bearer test-token"

    def test_partial_alias_errors_are_returned_not_raised(self) -> None:
        errors = [{"type": "NOT_FOUND", "path": ["r1"], "message": "Could not resolve"}]
        handler = ScriptedHandler(
            [graphql_success_response({"r0": repo_node("a/one"), "r1": None}, errors=errors)]
        )
        with make_client(handler) as client:
            result = client.execute(QUERY)
        assert result.data["r1"] is None
        assert result.errors == errors


class TestRateLimitFloor:
    def test_sleeps_until_reset_when_remaining_below_floor(self) -> None:
        reset_at = "2026-08-02T12:10:00+00:00"
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                graphql_success_response({}, remaining=150, reset_at=reset_at),
                graphql_success_response({}, remaining=5000),
            ]
        )
        with make_client(handler, sleep=sleep, rate_limit_floor=200) as client:
            client.execute(QUERY)
            assert sleep.calls == []
            client.execute(QUERY)
        assert sleep.calls == [600.0 + RESET_SLEEP_BUFFER_SECONDS]
        # The stale pre-pause state was dropped; the fresh response replaced it.
        assert client.last_rate_limit is not None
        assert client.last_rate_limit.remaining == 5000

    def test_no_pause_above_floor(self) -> None:
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                graphql_success_response({}, remaining=4000),
                graphql_success_response({}, remaining=3999),
            ]
        )
        with make_client(handler, sleep=sleep) as client:
            client.execute(QUERY)
            client.execute(QUERY)
        assert sleep.calls == []


class TestRetryAfter:
    def test_honors_retry_after_on_429(self) -> None:
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                httpx.Response(429, headers={"retry-after": "7"}, text="rate limited"),
                graphql_success_response({}),
            ]
        )
        with make_client(handler, sleep=sleep) as client:
            result = client.execute(QUERY)
        assert sleep.calls == [7.0]
        assert result.retries == 1

    def test_403_without_retry_after_backs_off(self) -> None:
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                httpx.Response(403, text="API rate limit exceeded"),
                graphql_success_response({}),
            ]
        )
        with make_client(handler, sleep=sleep) as client:
            client.execute(QUERY)
        assert len(sleep.calls) == 1
        assert 0.5 <= sleep.calls[0] <= 1.0  # backoff attempt 0 with jitter


class TestSecondaryLimit:
    def test_403_secondary_limit_stops_immediately(self) -> None:
        handler = ScriptedHandler(
            [httpx.Response(403, text="You have exceeded a secondary rate limit.")]
        )
        with make_client(handler) as client, pytest.raises(SecondaryRateLimitError):
            client.execute(QUERY)
        assert handler.call_count == 1  # no retry

    def test_graphql_error_secondary_limit_stops(self) -> None:
        errors = [{"type": "RATE_LIMITED", "message": "secondary rate limit hit"}]
        handler = ScriptedHandler([graphql_success_response({}, errors=errors)])
        with make_client(handler) as client, pytest.raises(SecondaryRateLimitError):
            client.execute(QUERY)


class TestBackoffAndFailure:
    def test_backs_off_on_5xx_then_succeeds(self) -> None:
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                httpx.Response(502, text="bad gateway"),
                httpx.Response(503, text="unavailable"),
                graphql_success_response({}),
            ]
        )
        with make_client(handler, sleep=sleep) as client:
            result = client.execute(QUERY)
        assert result.retries == 2
        assert len(sleep.calls) == 2
        assert 0.5 <= sleep.calls[0] <= 1.0
        assert 1.0 <= sleep.calls[1] <= 2.0

    def test_retries_exhausted_raises(self) -> None:
        handler = ScriptedHandler([httpx.Response(500, text="boom")] * 4)
        with (
            make_client(handler, max_retries=3) as client,
            pytest.raises(GraphQLRequestError, match="after 3 retries") as excinfo,
        ):
            client.execute(QUERY)
        assert excinfo.value.retries == 3
        assert handler.call_count == 4

    def test_transport_errors_are_retried(self) -> None:
        handler = ScriptedHandler([httpx.ConnectError("refused"), graphql_success_response({})])
        with make_client(handler) as client:
            result = client.execute(QUERY)
        assert result.retries == 1

    def test_malformed_json_200_is_retried_then_succeeds(self) -> None:
        # A proxy/CDN-mangled 200 body is a transient failure, not a crash.
        handler = ScriptedHandler(
            [
                httpx.Response(200, text="<html>gateway error</html>"),
                graphql_success_response({}),
            ]
        )
        with make_client(handler) as client:
            result = client.execute(QUERY)
        assert result.retries == 1

    def test_persistent_malformed_json_200_raises_request_error(self) -> None:
        handler = ScriptedHandler([httpx.Response(200, text="<html>gateway error</html>")] * 4)
        with (
            make_client(handler, max_retries=3) as client,
            pytest.raises(GraphQLRequestError, match="malformed JSON body"),
        ):
            client.execute(QUERY)

    def test_non_object_json_200_raises_request_error(self) -> None:
        handler = ScriptedHandler([httpx.Response(200, json=["not", "an", "object"])] * 4)
        with (
            make_client(handler, max_retries=3) as client,
            pytest.raises(GraphQLRequestError, match="non-object JSON body"),
        ):
            client.execute(QUERY)

    def test_no_data_raises(self) -> None:
        handler = ScriptedHandler(
            [httpx.Response(200, json={"errors": [{"message": "Something went wrong"}]})]
        )
        with make_client(handler) as client, pytest.raises(GraphQLRequestError, match="no data"):
            client.execute(QUERY)


class TestAuthentication:
    def test_401_fails_immediately_with_instructions(self) -> None:
        handler = ScriptedHandler([httpx.Response(401, text="Bad credentials")])
        with (
            make_client(handler) as client,
            pytest.raises(GitHubAuthenticationError, match="GITHUB_TOKEN"),
        ):
            client.execute(QUERY)
        assert handler.call_count == 1  # never retried


class TestConcurrencyBound:
    @pytest.mark.parametrize("value", [0, 3, 10])
    def test_concurrency_above_spec_cap_rejected(self, value: int) -> None:
        with pytest.raises(ValueError, match="max_concurrency"):
            GraphQLClient("t", max_concurrency=value)
