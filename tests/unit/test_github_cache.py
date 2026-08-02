"""Response cache tests: hashing stability, hits, and version invalidation."""

from __future__ import annotations

import json
from pathlib import Path

from codetalent.github.cache import ResponseCache, repository_batch_hash, request_hash

REPOS = ["b/two", "a/one", "c/three"]


class TestRequestHash:
    def test_key_order_does_not_matter(self) -> None:
        assert request_hash({"a": 1, "b": 2}) == request_hash({"b": 2, "a": 1})

    def test_different_payloads_differ(self) -> None:
        assert request_hash({"a": 1}) != request_hash({"a": 2})


class TestRepositoryBatchHash:
    def test_repo_order_does_not_matter(self) -> None:
        assert repository_batch_hash(REPOS, query_version="v1") == repository_batch_hash(
            list(reversed(REPOS)), query_version="v1"
        )

    def test_version_bump_invalidates(self) -> None:
        assert repository_batch_hash(REPOS, query_version="v1") != repository_batch_hash(
            REPOS, query_version="v2"
        )

    def test_different_batches_differ(self) -> None:
        assert repository_batch_hash(REPOS, query_version="v1") != repository_batch_hash(
            REPOS[:2], query_version="v1"
        )


class TestResponseCache:
    def test_miss_returns_none(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        assert cache.get("deadbeef") is None

    def test_put_get_round_trip(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        payload = {"data": {"r0": {"stargazerCount": 1}}, "errors": []}
        cache.put("abc123", payload)
        assert cache.get("abc123") == payload

    def test_files_are_valid_json_under_hash_name(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("abc123", {"data": {}})
        path = tmp_path / "cache" / "abc123.json"
        assert path.exists()
        assert json.loads(path.read_text()) == {"data": {}}

    def test_corrupt_file_treated_as_miss(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path / "cache")
        cache.put("abc123", {"data": {}})
        (tmp_path / "cache" / "abc123.json").write_text("{truncated")
        assert cache.get("abc123") is None
