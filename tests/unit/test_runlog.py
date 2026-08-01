"""Structured run-log tests: valid JSON lines carrying the spec section 26 fields."""

from __future__ import annotations

import io
import json

from codetalent.runlog import LOG_FIELDS, RunLogger, log_step, new_run_id


class TestLogStep:
    def test_emits_one_valid_json_line_with_all_fields(self) -> None:
        buffer = io.StringIO()
        log_step(
            run_id="abc123",
            phase="discovery",
            step="extract-events",
            status="completed",
            records_in=1000,
            records_out=950,
            cache_hits=10,
            api_cost=0.0,
            bytes_processed=52_428_800,
            duration_seconds=12.5,
            stream=buffer,
        )
        lines = buffer.getvalue().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert set(record) == set(LOG_FIELDS)
        assert record["run_id"] == "abc123"
        assert record["phase"] == "discovery"
        assert record["step"] == "extract-events"
        assert record["status"] == "completed"
        assert record["records_out"] == 950
        assert record["error_type"] is None

    def test_optional_fields_default_to_null(self) -> None:
        buffer = io.StringIO()
        record = log_step(run_id="abc123", phase="p", step="s", status="started", stream=buffer)
        parsed = json.loads(buffer.getvalue())
        assert parsed == record
        assert parsed["records_in"] is None
        assert parsed["bytes_processed"] is None


class TestRunLogger:
    def test_timed_step_logs_start_and_completion(self) -> None:
        buffer = io.StringIO()
        logger = RunLogger("pipeline-pilot", stream=buffer)
        with logger.timed("config-validation"):
            pass
        records = [json.loads(line) for line in buffer.getvalue().splitlines()]
        assert [r["status"] for r in records] == ["started", "completed"]
        assert all(r["run_id"] == logger.run_id for r in records)
        assert records[1]["duration_seconds"] >= 0.0

    def test_timed_step_logs_failure_and_reraises(self) -> None:
        buffer = io.StringIO()
        logger = RunLogger("pipeline-pilot", stream=buffer)
        try:
            with logger.timed("boom"):
                raise ValueError("nope")
        except ValueError:
            pass
        else:  # pragma: no cover - the exception must propagate
            raise AssertionError("expected ValueError to propagate")
        records = [json.loads(line) for line in buffer.getvalue().splitlines()]
        assert [r["status"] for r in records] == ["started", "failed"]
        assert records[1]["error_type"] == "ValueError"

    def test_run_ids_are_unique(self) -> None:
        assert new_run_id() != new_run_id()
