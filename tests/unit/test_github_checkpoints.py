"""Checkpoint store tests: round trip, resume semantics, retry caps."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codetalent.github.checkpoints import CheckpointStore, FailureRecord
from codetalent.github.rate_limit import RateLimitState


def make_store(tmp_path: Path) -> CheckpointStore:
    return CheckpointStore(tmp_path / "checkpoints" / "repositories.json")


class TestFreshStore:
    def test_defaults(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        assert store.completed_ids() == set()
        assert store.failed_records() == {}
        assert store.batch_size == 10
        assert store.last_rate_limit is None


class TestRoundTrip:
    def test_record_batch_persists_and_reloads(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        state = RateLimitState(
            "graphql",
            remaining=4900,
            reset_at=datetime(2026, 8, 2, 13, 0, tzinfo=UTC),
            limit=5000,
            last_cost=1,
        )
        store.record_batch(
            ["a/one", "b/two"], {"c/three": "NOT_FOUND"}, rate_limit=state, batch_size=25
        )

        reloaded = make_store(tmp_path)
        assert reloaded.completed_ids() == {"a/one", "b/two"}
        assert reloaded.failed_records() == {
            "c/three": FailureRecord(retries=1, reason="NOT_FOUND")
        }
        assert reloaded.batch_size == 25
        assert reloaded.last_rate_limit == state

    def test_success_removes_prior_failure(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        store.record_batch([], {"a/one": "REQUEST_ERROR:GraphQLRequestError"})
        store.record_batch(["a/one"], {})
        assert store.completed_ids() == {"a/one"}
        assert store.failed_records() == {}


class TestRetries:
    def test_failure_retries_increment(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        for _ in range(3):
            store.record_batch([], {"a/one": "REQUEST_ERROR:Timeout"})
        assert store.failed_records()["a/one"].retries == 3

    def test_retriable_respects_cap(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        store.record_batch([], {"a/one": "REQUEST_ERROR:Timeout", "b/two": "REQUEST_ERROR:Timeout"})
        store.record_batch([], {"b/two": "REQUEST_ERROR:Timeout"})
        assert store.retriable_failures(max_retries=2) == ["a/one"]
        assert store.retriable_failures(max_retries=1) == []

    def test_not_found_is_never_retried(self, tmp_path: Path) -> None:
        store = make_store(tmp_path)
        store.record_batch([], {"gone/repo": "NOT_FOUND"})
        assert store.retriable_failures(max_retries=99) == []
