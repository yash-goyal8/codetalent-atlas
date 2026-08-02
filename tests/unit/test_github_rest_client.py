"""REST client tests: header parsing, Retry-After, auth failure, secondary limits."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import httpx
import pytest
from _github_fakes import ScriptedHandler, SleepRecorder

from codetalent.github.graphql_client import GitHubAuthenticationError, SecondaryRateLimitError
from codetalent.github.rest_client import RestClient

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)


def make_client(handler: ScriptedHandler, *, sleep: SleepRecorder | None = None) -> RestClient:
    return RestClient(
        "test-token",
        transport=httpx.MockTransport(handler),
        sleep=sleep if sleep is not None else SleepRecorder(),
        rng=random.Random(3),
        now=lambda: NOW,
    )


class TestGet:
    def test_returns_json_and_parses_rate_limit_headers(self) -> None:
        handler = ScriptedHandler(
            [
                httpx.Response(
                    200,
                    json={"name": "kubernetes"},
                    headers={
                        "x-ratelimit-remaining": "4321",
                        "x-ratelimit-reset": str(int(NOW.timestamp()) + 600),
                        "x-ratelimit-limit": "5000",
                    },
                )
            ]
        )
        with make_client(handler) as client:
            payload = client.get("/repos/kubernetes/kubernetes")
        assert payload == {"name": "kubernetes"}
        assert client.last_rate_limit is not None
        assert client.last_rate_limit.remaining == 4321
        request = handler.requests[0]
        assert request.headers["authorization"] == "bearer test-token"
        assert str(request.url) == "https://api.github.com/repos/kubernetes/kubernetes"

    def test_honors_retry_after(self) -> None:
        sleep = SleepRecorder()
        handler = ScriptedHandler(
            [
                httpx.Response(429, headers={"retry-after": "11"}, text="slow down"),
                httpx.Response(200, json={}),
            ]
        )
        with make_client(handler, sleep=sleep) as client:
            client.get("/rate_limit")
        assert sleep.calls == [11.0]

    def test_401_fails_immediately(self) -> None:
        handler = ScriptedHandler([httpx.Response(401, text="Bad credentials")])
        with make_client(handler) as client, pytest.raises(GitHubAuthenticationError):
            client.get("/rate_limit")
        assert handler.call_count == 1

    def test_secondary_limit_stops(self) -> None:
        handler = ScriptedHandler(
            [httpx.Response(403, text="You have exceeded a secondary rate limit")]
        )
        with make_client(handler) as client, pytest.raises(SecondaryRateLimitError):
            client.get("/rate_limit")
