"""User-profile enrichment tests (spec 9.5): mocked HTTP, privacy assertions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl
import pytest

from codetalent.github.enrich_users import (
    enrich_users,
    load_user_worklist,
    profile_from_node,
    write_profiles_atomic,
)
from codetalent.github.graphql_client import GraphQLClient
from codetalent.github.query_builder import build_user_batch_query
from codetalent.schemas import AccountType, FetchStatus, UserProfile

NOW = datetime(2026, 8, 2, tzinfo=UTC)


class TestUserBatchQuery:
    def test_privacy_no_forbidden_fields(self) -> None:
        import re

        built = build_user_batch_query(["alice", "bob-2"])
        # Token-boundary match: "__typename" must not trip the "name" check.
        for forbidden in ("email", "name", "company", "websiteUrl", "organizations"):
            assert not re.search(rf"(?<![\w_]){forbidden}(?![\w_])", built.query), forbidden
        assert "location" in built.query
        assert "createdAt" in built.query
        assert "followers { totalCount }" in built.query

    def test_alias_map_sorted_and_deduplicated(self) -> None:
        built = build_user_batch_query(["zed", "alice", "zed"])
        assert built.alias_to_login == {"u0": "alice", "u1": "zed"}

    def test_invalid_login_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid GitHub login"):
            build_user_batch_query(["bad login!"])


class TestProfileFromNode:
    def test_user_node(self) -> None:
        node = {
            "__typename": "User",
            "login": "alice",
            "location": "Berlin, Germany",
            "createdAt": "2019-01-01T00:00:00Z",
            "followers": {"totalCount": 42},
        }
        row = profile_from_node("alice", node, NOW)
        assert row.account_type is AccountType.USER
        assert row.public_location_raw == "Berlin, Germany"
        assert row.followers_count == 42
        assert row.fetch_status is FetchStatus.SUCCESS

    def test_organization_node_has_no_location(self) -> None:
        row = profile_from_node("acme", {"__typename": "Organization", "login": "acme"}, NOW)
        assert row.account_type is AccountType.ORGANIZATION
        assert row.public_location_raw is None

    def test_null_node_is_not_found(self) -> None:
        row = profile_from_node("ghost", None, NOW)
        assert row.fetch_status is FetchStatus.NOT_FOUND
        assert row.account_type is AccountType.UNKNOWN


class TestWorklist:
    def test_qualified_filter_restricts(self, tmp_path: Path) -> None:
        activity = tmp_path / "activity.parquet"
        pl.DataFrame(
            {"actor_login": ["a", "b", "c"], "repo_name": ["o/r1", "o/r2", "o/r1"]}
        ).write_parquet(activity)
        qualified = tmp_path / "classification.parquet"
        pl.DataFrame(
            {"repo_name": ["o/r1", "o/r2"], "classification_status": ["accepted", "rejected"]}
        ).write_parquet(qualified)
        assert load_user_worklist(activity, qualified) == ["a", "c"]
        assert load_user_worklist(activity, None) == ["a", "b", "c"]


class TestWriteProfilesAtomic:
    def test_dedupe_keeps_latest(self, tmp_path: Path) -> None:
        path = tmp_path / "profiles.parquet"
        early = UserProfile(
            actor_login="a",
            account_type=AccountType.USER,
            public_location_raw="Old",
            profile_fetched_at=NOW,
            fetch_status=FetchStatus.SUCCESS,
        )
        late = early.model_copy(
            update={"public_location_raw": "New", "profile_fetched_at": NOW.replace(hour=5)}
        )
        write_profiles_atomic([early], path)
        assert write_profiles_atomic([late], path) == 1
        assert pl.read_parquet(path)["public_location_raw"].to_list() == ["New"]


def _graphql_response(data: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "rateLimit": {
                    "limit": 5000,
                    "cost": 1,
                    "remaining": 4999,
                    "resetAt": "2026-08-02T23:00:00Z",
                },
                **data,
            }
        },
    )


class TestEnrichUsersEndToEnd:
    def test_two_batches_with_org_and_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        activity = tmp_path / "activity.parquet"
        logins = [f"user{i:02d}" for i in range(12)]
        pl.DataFrame({"actor_login": logins, "repo_name": ["o/r"] * 12}).write_parquet(activity)

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            # Reconstruct which aliases were requested from the query text.
            query: str = body["query"]
            data: dict[str, object] = {}
            for line in query.splitlines():
                line = line.strip()
                if line.startswith("u") and ": repositoryOwner" in line:
                    alias, rest = line.split(":", 1)
                    login = rest.split('login: "')[1].split('"')[0]
                    if login == "user03":
                        data[alias] = None  # deleted account
                    elif login == "user05":
                        data[alias] = {"__typename": "Organization", "login": login}
                    else:
                        data[alias] = {
                            "__typename": "User",
                            "login": login,
                            "location": "Berlin, Germany",
                            "createdAt": "2020-05-05T00:00:00Z",
                            "followers": {"totalCount": 7},
                        }
            return _graphql_response(data)

        client = GraphQLClient(
            "test-token", transport=httpx.MockTransport(handler), sleep=lambda _s: None
        )
        report = enrich_users(
            activity_path=activity,
            qualified_path=None,
            output_path=tmp_path / "profiles.parquet",
            checkpoint_path=tmp_path / "cp.json",
            cache_dir=tmp_path / "cache",
            usage_report_path=tmp_path / "usage.csv",
            client=client,
        )
        assert report.worklist_total == 12
        assert report.succeeded == 12
        written = pl.read_parquet(tmp_path / "profiles.parquet")
        assert written.height == 12
        statuses = dict(zip(written["actor_login"], written["fetch_status"], strict=True))
        assert statuses["user03"] == "not_found"
        types = dict(zip(written["actor_login"], written["account_type"], strict=True))
        assert types["user05"] == "organization"
        assert types["user00"] == "user"
        # Ledger rows carry the users resource type.
        usage = (tmp_path / "usage.csv").read_text()
        assert "graphql_users" in usage

        # Resume: a second run fetches nothing new (checkpoint skips all).
        client2 = GraphQLClient(
            "test-token",
            transport=httpx.MockTransport(
                lambda _r: (_ for _ in ()).throw(AssertionError("unexpected HTTP request"))
            ),
            sleep=lambda _s: None,
        )
        resumed = enrich_users(
            activity_path=activity,
            qualified_path=None,
            output_path=tmp_path / "profiles.parquet",
            checkpoint_path=tmp_path / "cp.json",
            cache_dir=tmp_path / "cache",
            usage_report_path=tmp_path / "usage.csv",
            client=client2,
        )
        assert resumed.attempted == 0
        assert resumed.already_completed == 12
