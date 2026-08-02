"""Fake BigQuery client machinery for unit tests.

pytest never talks to live BigQuery (CI has no GCP credentials): every test
injects these fakes, which mimic the small google-cloud-bigquery surface the
runner and export modules use, while recording calls for order and
job-configuration assertions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa
from google.api_core.exceptions import NotFound
from google.cloud import bigquery


@dataclass
class FakeJob:
    """Stands in for a QueryJob (dry-run or executed)."""

    total_bytes_processed: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)
    error: Exception | None = None

    def result(self) -> list[dict[str, Any]]:
        if self.error is not None:
            raise self.error
        return self.rows


@dataclass
class FakeTable:
    """Stands in for a Table returned by get_table."""

    table_id: str
    num_rows: int = 0
    schema: list[bigquery.SchemaField] = field(default_factory=list)


class FakeRowIterator:
    """REST row iterator; records the create_bqstorage_client argument."""

    def __init__(self, arrow_table: pa.Table) -> None:
        self._arrow = arrow_table
        self.bqstorage_requests: list[Any] = []

    def to_arrow(self, create_bqstorage_client: bool = True) -> pa.Table:
        self.bqstorage_requests.append(create_bqstorage_client)
        return self._arrow


class FakeClient:
    """Configurable fake for bigquery.Client.

    * ``dry_run_bytes``: estimate returned for dry-run jobs, or a callable
      ``sql -> int`` (raise NotFound inside it to simulate missing tables).
    * ``tables``: table_id -> FakeTable for get_table.
    * ``arrow_tables``: table_id -> pyarrow.Table served by list_rows.
    * ``fetch_rows``: rows returned by executed jobs (quality checks).
    * Executed materializations register their destination in ``tables``.
    """

    def __init__(
        self,
        *,
        dry_run_bytes: int | Any = 1000,
        tables: dict[str, FakeTable] | None = None,
        arrow_tables: dict[str, pa.Table] | None = None,
        fetch_rows: list[dict[str, Any]] | None = None,
        execution_error: Exception | None = None,
    ) -> None:
        self.dry_run_bytes = dry_run_bytes
        self.tables = tables if tables is not None else {}
        self.arrow_tables = arrow_tables if arrow_tables is not None else {}
        self.fetch_rows = fetch_rows if fetch_rows is not None else []
        self.execution_error = execution_error
        self.calls: list[tuple[str, Any]] = []
        self.datasets: dict[str, bigquery.Dataset] = {}
        self.row_iterators: list[FakeRowIterator] = []

    # -- client surface used by the runner ----------------------------------

    def query(
        self,
        sql: str,
        job_config: bigquery.QueryJobConfig | None = None,
        location: str | None = None,
    ) -> FakeJob:
        if job_config is not None and job_config.dry_run:
            self.calls.append(("dry_run", job_config))
            estimate = (
                self.dry_run_bytes(sql) if callable(self.dry_run_bytes) else self.dry_run_bytes
            )
            return FakeJob(total_bytes_processed=int(estimate))
        self.calls.append(("execute", job_config))
        if self.execution_error is not None:
            return FakeJob(error=self.execution_error)
        destination = getattr(job_config, "destination", None) if job_config else None
        if destination is not None:
            table_id = f"{destination.project}.{destination.dataset_id}.{destination.table_id}"
            self.tables[table_id] = FakeTable(table_id=table_id, num_rows=1)
        estimate = self.dry_run_bytes(sql) if callable(self.dry_run_bytes) else self.dry_run_bytes
        return FakeJob(total_bytes_processed=int(estimate), rows=list(self.fetch_rows))

    def get_table(self, table_id: str) -> FakeTable:
        self.calls.append(("get_table", table_id))
        if table_id not in self.tables:
            raise NotFound(f"table not found: {table_id}")
        return self.tables[table_id]

    def get_dataset(self, dataset_id: str) -> bigquery.Dataset:
        self.calls.append(("get_dataset", dataset_id))
        if dataset_id not in self.datasets:
            raise NotFound(f"dataset not found: {dataset_id}")
        return self.datasets[dataset_id]

    def create_dataset(
        self, dataset: bigquery.Dataset, exists_ok: bool = False
    ) -> bigquery.Dataset:
        self.calls.append(("create_dataset", dataset))
        self.datasets[f"{dataset.project}.{dataset.dataset_id}"] = dataset
        return dataset

    # -- client surface used by export --------------------------------------

    def list_rows(
        self,
        table: FakeTable,
        selected_fields: list[bigquery.SchemaField] | None = None,
    ) -> FakeRowIterator:
        self.calls.append(("list_rows", (table.table_id, selected_fields)))
        iterator = FakeRowIterator(self.arrow_tables[table.table_id])
        self.row_iterators.append(iterator)
        return iterator

    # -- helpers -------------------------------------------------------------

    def call_kinds(self) -> list[str]:
        return [kind for kind, _ in self.calls]

    def executed_configs(self) -> list[bigquery.QueryJobConfig]:
        return [config for kind, config in self.calls if kind == "execute"]


def register_arrow_table(client: FakeClient, table_id: str, arrow_table: pa.Table) -> None:
    """Register a table with a schema derived from an arrow table (for export)."""
    schema = [bigquery.SchemaField(name, "STRING") for name in arrow_table.column_names]
    client.tables[table_id] = FakeTable(
        table_id=table_id, num_rows=arrow_table.num_rows, schema=schema
    )
    client.arrow_tables[table_id] = arrow_table
