"""Fake GitHub GraphQL/REST transport machinery for unit tests.

pytest never talks to the live GitHub API: every test injects an
``httpx.MockTransport`` built from these helpers, which mimic the GraphQL
response envelope (aliased repository nodes, rateLimit block, partial errors)
while recording requests for order and payload assertions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

import httpx

_ALIAS_RE = re.compile(r'(r\d+): repository\(owner: "([^"]+)", name: "([^"]+)"\)')

RATE_LIMIT_RESET_AT = "2026-08-02T12:00:00+00:00"


def repo_node(name_with_owner: str, **overrides: Any) -> dict[str, Any]:
    """A full, realistic GraphQL repository node; override any field."""
    node: dict[str, Any] = {
        "nameWithOwner": name_with_owner,
        "isFork": False,
        "isArchived": False,
        "isDisabled": False,
        "description": f"Description of {name_with_owner}",
        "primaryLanguage": {"name": "Go"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "kubernetes"}}]},
        "stargazerCount": 42,
        "forkCount": 7,
        "licenseInfo": {"spdxId": "Apache-2.0"},
        "pushedAt": "2026-07-30T10:00:00Z",
        "updatedAt": "2026-07-31T10:00:00Z",
        "releases": {"totalCount": 3},
        "issues": {"totalCount": 11},
        "pullRequests": {"totalCount": 25},
        "readmeMd": {"__typename": "Blob"},
        "readmeRst": None,
        "readmeLower": None,
        "contributing": {"__typename": "Blob"},
        "codeOfConduct": None,
        "ciWorkflows": {"__typename": "Tree"},
        "testsDir": {"__typename": "Tree"},
        "testDir": None,
    }
    node.update(overrides)
    return node


def rate_limit_block(
    *,
    cost: int = 1,
    remaining: int = 4990,
    reset_at: str = RATE_LIMIT_RESET_AT,
    limit: int = 5000,
) -> dict[str, Any]:
    return {"limit": limit, "cost": cost, "remaining": remaining, "resetAt": reset_at}


def not_found_error(alias: str, name_with_owner: str) -> dict[str, Any]:
    return {
        "type": "NOT_FOUND",
        "path": [alias],
        "message": f"Could not resolve to a Repository with the name '{name_with_owner}'.",
    }


class FakeGitHubGraphQL:
    """Callable for ``httpx.MockTransport`` answering batched repository queries.

    Parses the aliased query out of each request and returns a full node per
    repository, ``null`` + a NOT_FOUND error for names in ``missing``, and a
    rateLimit block whose cost/remaining can vary per call.
    """

    def __init__(
        self,
        *,
        missing: Iterable[str] = (),
        node_overrides: Mapping[str, dict[str, Any]] | None = None,
        cost_for_batch: Callable[[int, int], int] | None = None,
        remaining_for_call: Callable[[int], int] | None = None,
        reset_at: str = RATE_LIMIT_RESET_AT,
        pad_response_bytes: int = 0,
    ) -> None:
        self.missing = set(missing)
        self.node_overrides = dict(node_overrides or {})
        self.cost_for_batch = cost_for_batch or (lambda _call, _batch_len: 1)
        self.remaining_for_call = remaining_for_call or (lambda _call: 4990)
        self.reset_at = reset_at
        self.pad_response_bytes = pad_response_bytes
        self.requests: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        self.requests.append(payload)
        call_index = len(self.requests)
        pairs = _ALIAS_RE.findall(payload["query"])
        data: dict[str, Any] = {
            "rateLimit": rate_limit_block(
                cost=self.cost_for_batch(call_index, len(pairs)),
                remaining=self.remaining_for_call(call_index),
                reset_at=self.reset_at,
            )
        }
        errors: list[dict[str, Any]] = []
        for alias, owner, name in pairs:
            full_name = f"{owner}/{name}"
            if full_name in self.missing:
                data[alias] = None
                errors.append(not_found_error(alias, full_name))
            else:
                data[alias] = repo_node(full_name, **self.node_overrides.get(full_name, {}))
        if self.pad_response_bytes:
            data["_padding"] = "x" * self.pad_response_bytes
        body: dict[str, Any] = {"data": data}
        if errors:
            body["errors"] = errors
        return httpx.Response(200, json=body)


class ScriptedHandler:
    """Callable for ``httpx.MockTransport`` replaying a fixed response script."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("ScriptedHandler exhausted: unexpected extra HTTP request")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def graphql_success_response(
    nodes: Mapping[str, dict[str, Any] | None],
    *,
    errors: list[dict[str, Any]] | None = None,
    cost: int = 1,
    remaining: int = 4990,
    reset_at: str = RATE_LIMIT_RESET_AT,
) -> httpx.Response:
    """A 200 GraphQL envelope with the given alias -> node map."""
    data: dict[str, Any] = {
        "rateLimit": rate_limit_block(cost=cost, remaining=remaining, reset_at=reset_at)
    }
    data.update(nodes)
    body: dict[str, Any] = {"data": data}
    if errors:
        body["errors"] = errors
    return httpx.Response(200, json=body)


class SleepRecorder:
    """Injectable ``sleep`` capturing every requested delay without sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
