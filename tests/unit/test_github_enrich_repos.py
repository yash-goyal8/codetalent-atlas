"""End-to-end enrichment orchestration tests over a fake GraphQL transport."""

from __future__ import annotations

import io
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl
import pytest
from _github_fakes import (
    FakeGitHubGraphQL,
    ScriptedHandler,
    SleepRecorder,
    graphql_success_response,
    repo_node,
)

from codetalent.github.checkpoints import CheckpointStore
from codetalent.github.enrich_repos import (
    USAGE_HEADER,
    EnrichmentReport,
    EnrichmentUsageLedger,
    ErrorRateExceededError,
    LedgerFormatError,
    WorklistError,
    enrich_repositories,
    load_worklist,
    next_batch_size,
    write_metadata_atomic,
)
from codetalent.github.graphql_client import (
    GitHubAuthenticationError,
    GraphQLClient,
    SecondaryRateLimitError,
)
from codetalent.runlog import RunLogger
from codetalent.schemas import RepositoryMetadata

NOW = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)

ACCEPTED = [f"owner{i:02d}/repo{i:02d}" for i in range(15)]
MISSING = "owner03/repo03"


@dataclass
class Paths:
    worklist: Path
    output: Path
    checkpoint: Path
    cache: Path
    ledger: Path


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    worklist = tmp_path / "repository_activity_summary.parquet"
    rows = [{"repo_name": name, "discovery_status": "accepted"} for name in ACCEPTED]
    rows.append({"repo_name": "excluded/repo", "discovery_status": "excluded"})
    rows.append({"repo_name": "candidate/repo", "discovery_status": "below_candidate_floor"})
    pl.DataFrame(rows).write_parquet(worklist)
    return Paths(
        worklist=worklist,
        output=tmp_path / "repository_metadata.parquet",
        checkpoint=tmp_path / "checkpoints" / "repositories.json",
        cache=tmp_path / "cache",
        ledger=tmp_path / "enrichment_usage.csv",
    )


def make_client(handler: FakeGitHubGraphQL | ScriptedHandler) -> GraphQLClient:
    return GraphQLClient(
        "test-token",
        transport=httpx.MockTransport(handler),
        sleep=SleepRecorder(),
        rng=random.Random(11),
        now=lambda: NOW,
    )


def run(
    paths: Paths,
    handler: FakeGitHubGraphQL | ScriptedHandler,
    **kwargs: object,
) -> EnrichmentReport:
    return enrich_repositories(
        input_path=paths.worklist,
        output_path=paths.output,
        checkpoint_path=paths.checkpoint,
        cache_dir=paths.cache,
        usage_report_path=paths.ledger,
        client=make_client(handler),
        logger=RunLogger("test-enrich", stream=io.StringIO()),
        **kwargs,  # type: ignore[arg-type]
    )


class TestLoadWorklist:
    def test_accepted_only_sorted_unique(self, paths: Paths) -> None:
        assert load_worklist(paths.worklist) == ACCEPTED

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(WorklistError, match="worklist not found"):
            load_worklist(tmp_path / "nope.parquet")


class TestEndToEnd:
    def test_two_batches_with_one_deleted_repo(self, paths: Paths) -> None:
        handler = FakeGitHubGraphQL(missing={MISSING})
        report = run(paths, handler, error_rate_min_sample=1)

        assert handler.call_count == 2  # 10 + 5 repositories
        assert report.worklist_total == 15
        assert report.attempted == 15
        assert report.succeeded == 14
        assert report.failed == 1
        assert report.cache_hits == 0
        assert report.total_rows == 14
        assert report.output_path == paths.output

        # Parquet output validates row-for-row through the spec 9.2 model.
        frame = pl.read_parquet(paths.output)
        assert frame.height == 14
        names = frame.get_column("repo_name").to_list()
        assert names == sorted(names)
        assert MISSING not in names
        for row in frame.to_dicts():
            metadata = RepositoryMetadata(**row)
            assert metadata.has_readme is True
            assert metadata.has_contributing is True
            assert metadata.has_code_of_conduct is False
            assert metadata.has_ci is True
            assert metadata.has_tests_signal is True
            assert metadata.topics == ["kubernetes"]
            assert metadata.graphql_fetched_at.tzinfo is not None

        # Deleted repo is quarantined in the checkpoint with its reason.
        checkpoint = CheckpointStore(paths.checkpoint)
        assert len(checkpoint.completed_ids()) == 14
        failure = checkpoint.failed_records()[MISSING]
        assert failure.reason == "NOT_FOUND"
        assert failure.retries == 1

        # Every response was cached.
        assert len(list(paths.cache.glob("*.json"))) == 2

    def test_ledger_rows_match_required_header(self, paths: Paths) -> None:
        run(paths, FakeGitHubGraphQL(missing={MISSING}))
        lines = paths.ledger.read_text().strip().splitlines()
        expected_header = (
            "timestamp,resource_type,batch_size,query_cost,"
            "remaining,reset_at,status,retries,cache_hit"
        )
        assert lines[0] == expected_header
        assert len(lines) == 3  # header + one row per request
        first = lines[1].split(",")
        assert first[1] == "graphql_repositories"
        assert first[2] == "10"
        assert first[3] == "1"
        assert first[4] == "4990"
        assert first[6] == "success"
        assert first[8] == "false"
        second = lines[2].split(",")
        assert second[2] == "5"

    def test_not_found_does_not_trip_error_rate(self, paths: Paths) -> None:
        # 1 deleted repo out of 15 is 6.7% — far above 1% — but NOT_FOUND is an
        # expected transition and must not stop the run.
        report = run(
            paths,
            FakeGitHubGraphQL(missing={MISSING}),
            error_rate_min_sample=1,
            max_error_rate=0.01,
        )
        assert report.failed == 1


class TestResume:
    def test_resume_never_refetches_completed_records(self, paths: Paths) -> None:
        run(paths, FakeGitHubGraphQL(missing={MISSING}))

        # Second run: any HTTP request would exhaust the empty script and fail.
        empty = ScriptedHandler([])
        report = run(paths, empty)
        assert empty.call_count == 0
        assert report.attempted == 0
        assert report.already_completed == 14
        assert report.total_rows == 14  # prior output intact

    def test_transient_failures_retried_up_to_cap(self, paths: Paths) -> None:
        checkpoint = CheckpointStore(paths.checkpoint)
        checkpoint.record_batch([], {ACCEPTED[0]: "REQUEST_ERROR:GraphQLRequestError"})

        handler = FakeGitHubGraphQL()
        report = run(paths, handler)
        assert report.attempted == 15  # failed record was re-included and now succeeded
        reloaded = CheckpointStore(paths.checkpoint)
        assert ACCEPTED[0] in reloaded.completed_ids()
        assert ACCEPTED[0] not in reloaded.failed_records()

    def test_exhausted_failures_stay_quarantined_and_are_surfaced(self, paths: Paths) -> None:
        checkpoint = CheckpointStore(paths.checkpoint)
        for _ in range(3):
            checkpoint.record_batch([], {ACCEPTED[0]: "REQUEST_ERROR:GraphQLRequestError"})

        handler = FakeGitHubGraphQL()
        report = run(paths, handler, max_failure_retries=3)
        assert report.attempted == 14
        assert ACCEPTED[0] not in CheckpointStore(paths.checkpoint).completed_ids()
        # The silently skipped record is surfaced, so "done" is
        # distinguishable from "done except abandoned records".
        assert report.exhausted_failures == {ACCEPTED[0]: "REQUEST_ERROR:GraphQLRequestError"}

    def test_raising_max_failure_retries_reincludes_exhausted_records(self, paths: Paths) -> None:
        checkpoint = CheckpointStore(paths.checkpoint)
        for _ in range(3):
            checkpoint.record_batch([], {ACCEPTED[0]: "REQUEST_ERROR:GraphQLRequestError"})

        report = run(paths, FakeGitHubGraphQL(), max_failure_retries=4)
        assert report.attempted == 15
        assert ACCEPTED[0] in CheckpointStore(paths.checkpoint).completed_ids()
        assert report.exhausted_failures == {}

    def test_permanent_not_found_is_not_reported_as_exhausted(self, paths: Paths) -> None:
        checkpoint = CheckpointStore(paths.checkpoint)
        for _ in range(3):
            checkpoint.record_batch([], {MISSING: "NOT_FOUND"})

        report = run(paths, FakeGitHubGraphQL(missing={MISSING}), max_failure_retries=3)
        assert report.exhausted_failures == {}


class TestCache:
    def test_cache_hits_avoid_http_entirely(self, paths: Paths) -> None:
        run(paths, FakeGitHubGraphQL(missing={MISSING}))
        # Fresh checkpoint, warm cache: identical batches replay from disk.
        paths.checkpoint.unlink()

        empty = ScriptedHandler([])
        report = run(paths, empty)
        assert empty.call_count == 0
        assert report.cache_hits == 2
        assert report.attempted == 15
        assert report.succeeded == 14

        lines = paths.ledger.read_text().strip().splitlines()
        cached_rows = [line.split(",") for line in lines[3:]]
        assert len(cached_rows) == 2
        for row in cached_rows:
            assert row[3] == "0"  # no API cost
            assert row[6] == "success"
            assert row[8] == "true"


class TestLimit:
    def test_limit_caps_attempted_repositories(self, paths: Paths) -> None:
        handler = FakeGitHubGraphQL()
        report = run(paths, handler, limit=10)
        assert handler.call_count == 1
        assert report.attempted == 10
        assert report.succeeded == 10
        assert len(CheckpointStore(paths.checkpoint).completed_ids()) == 10


class TestBatchAdaptation:
    def test_next_batch_size_rules(self) -> None:
        one_mib = 1024 * 1024
        assert next_batch_size(10, cost=1, response_bytes=1000, batch_len=10) == 25
        assert next_batch_size(25, cost=2, response_bytes=1000, batch_len=25) == 50
        assert next_batch_size(50, cost=5, response_bytes=1000, batch_len=50) == 50
        assert next_batch_size(25, cost=5, response_bytes=1000, batch_len=25) == 10
        assert next_batch_size(25, cost=1, response_bytes=one_mib + 1, batch_len=25) == 10
        assert next_batch_size(50, cost=None, response_bytes=0, batch_len=50) == 50
        # Partial tail batches are unrepresentative and never change the size.
        assert next_batch_size(25, cost=1, response_bytes=1000, batch_len=5) == 25

    def test_cheap_batches_grow_and_size_persists(self, paths: Paths) -> None:
        handler = FakeGitHubGraphQL()
        report = run(paths, handler)
        # Batch 1 (10 repos, cost 1) grows the size to 25, so batch 2 takes the
        # remaining 5 in one request.
        assert [
            len(request["query"].split("repository(owner:")) - 1 for request in handler.requests
        ] == [10, 5]
        assert report.batch_size == 25
        assert CheckpointStore(paths.checkpoint).batch_size == 25

    def test_expensive_batches_fall_back_to_10(self, paths: Paths) -> None:
        # 35 repos: batch 1 (10, cheap) grows to 25; batch 2 (a full 25, cost 9)
        # exceeds 1 point per ~10 repos and falls back to 10.
        names = [f"big{i:02d}/repo{i:02d}" for i in range(35)]
        pl.DataFrame(
            [{"repo_name": name, "discovery_status": "accepted"} for name in names]
        ).write_parquet(paths.worklist)
        handler = FakeGitHubGraphQL(cost_for_batch=lambda call, batch_len: 1 if call == 1 else 9)
        report = run(paths, handler)
        assert [
            len(request["query"].split("repository(owner:")) - 1 for request in handler.requests
        ] == [10, 25]
        assert report.batch_size == 10
        assert CheckpointStore(paths.checkpoint).batch_size == 10


class TestFailurePolicies:
    def test_error_rate_exceeded_stops_with_checkpoint_preserved(self, paths: Paths) -> None:
        handler = FakeGitHubGraphQL(node_overrides={ACCEPTED[1]: {"stargazerCount": None}})
        with pytest.raises(ErrorRateExceededError, match="exceeds"):
            run(paths, handler, error_rate_min_sample=1, max_error_rate=0.01)
        checkpoint = CheckpointStore(paths.checkpoint)
        assert len(checkpoint.completed_ids()) == 9
        assert checkpoint.failed_records()[ACCEPTED[1]].reason.startswith("PARSE_ERROR:")

    def test_secondary_limit_stops_and_preserves_checkpoint(self, paths: Paths) -> None:
        first_batch = {f"r{i}": repo_node(name) for i, name in enumerate(ACCEPTED[:10])}
        handler = ScriptedHandler(
            [
                graphql_success_response(first_batch),
                httpx.Response(403, text="You have exceeded a secondary rate limit."),
            ]
        )
        with pytest.raises(SecondaryRateLimitError):
            run(paths, handler)
        assert len(CheckpointStore(paths.checkpoint).completed_ids()) == 10

        lines = paths.ledger.read_text().strip().splitlines()
        assert lines[-1].split(",")[6] == "secondary_limit"

    def test_401_mid_run_writes_ledger_row_before_raising(self, paths: Paths) -> None:
        first_batch = {f"r{i}": repo_node(name) for i, name in enumerate(sorted(ACCEPTED)[:10])}
        handler = ScriptedHandler(
            [
                graphql_success_response(first_batch),
                httpx.Response(401, text="Bad credentials"),
            ]
        )
        with pytest.raises(GitHubAuthenticationError):
            run(paths, handler)
        # One row per issued request (API-safety rule 5): the spent 401
        # request must leave an accounting trail too.
        lines = paths.ledger.read_text().strip().splitlines()
        assert len(lines) == 3  # header + success + auth_error
        last = lines[-1].split(",")
        assert last[6] == "auth_error"
        assert last[3] == "0"
        assert last[8] == "false"
        # The completed batch's checkpoint is preserved.
        assert len(CheckpointStore(paths.checkpoint).completed_ids()) == 10

    def test_malformed_200_body_is_ledgered_and_quarantined(self, paths: Paths) -> None:
        # A persistent proxy/CDN-mangled 200 body must not crash the run: the
        # batch fails through GraphQLRequestError, gets a ledger row, is
        # quarantined in the checkpoint, and the run continues.
        first_batch = {f"r{i}": repo_node(name) for i, name in enumerate(sorted(ACCEPTED)[:10])}
        handler = ScriptedHandler(
            [graphql_success_response(first_batch)]
            + [httpx.Response(200, text="<html>gateway error</html>")] * 6  # initial + 5 retries
        )
        report = run(paths, handler)
        assert report.succeeded == 10
        assert report.failed == 5
        lines = paths.ledger.read_text().strip().splitlines()
        assert [line.split(",")[6] for line in lines[1:]] == ["success", "error"]
        checkpoint = CheckpointStore(paths.checkpoint)
        assert len(checkpoint.completed_ids()) == 10
        for name in sorted(ACCEPTED)[10:]:
            assert checkpoint.failed_records()[name].reason == "REQUEST_ERROR:GraphQLRequestError"


class TestWriteMetadataAtomic:
    def _row(self, fetched_at: datetime, stars: int) -> RepositoryMetadata:
        return RepositoryMetadata(
            repo_name="a/one",
            is_fork=False,
            is_archived=False,
            is_disabled=False,
            topics=["iac"],
            stargazer_count=stars,
            fork_count=0,
            release_count=0,
            issue_count=0,
            pull_request_count=0,
            graphql_fetched_at=fetched_at,
        )

    def test_dedupes_by_repo_name_keeping_latest(self, tmp_path: Path) -> None:
        path = tmp_path / "metadata.parquet"
        write_metadata_atomic([self._row(NOW, stars=1)], path)
        later = NOW.replace(hour=13)
        assert write_metadata_atomic([self._row(later, stars=2)], path) == 1
        frame = pl.read_parquet(path)
        assert frame.height == 1
        assert frame.get_column("stargazer_count").to_list() == [2]

    def test_no_leftover_temp_files(self, tmp_path: Path) -> None:
        path = tmp_path / "metadata.parquet"
        write_metadata_atomic([self._row(NOW, stars=1)], path)
        assert [p.name for p in tmp_path.iterdir()] == ["metadata.parquet"]


class TestLedgerFormat:
    def test_wrong_header_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "enrichment_usage.csv"
        path.write_text("timestamp,wrong,header\n")
        ledger = EnrichmentUsageLedger(path)
        with pytest.raises(LedgerFormatError):
            ledger.append(
                resource_type="graphql_repositories",
                batch_size=10,
                query_cost=1,
                remaining=100,
                reset_at="",
                status="success",
                retries=0,
                cache_hit=False,
            )

    def test_header_constant_matches_spec(self) -> None:
        assert ",".join(USAGE_HEADER) == (
            "timestamp,resource_type,batch_size,query_cost,remaining,reset_at,status,retries,cache_hit"
        )


class TestCachedNotFoundReplay:
    def test_cached_batch_replays_not_found_consistently(self, paths: Paths) -> None:
        run(paths, FakeGitHubGraphQL(missing={MISSING}))
        cached_files = list(paths.cache.glob("*.json"))
        assert any("NOT_FOUND" in json.dumps(json.loads(p.read_text())) for p in cached_files)
