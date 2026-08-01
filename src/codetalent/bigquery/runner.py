"""BigQuery query runner with a mandatory maximum-bytes guard.

Executes discovery SQL against the GH Archive public dataset in a BigQuery
Sandbox project (no billing) and records estimated and actual bytes in
``reports/query_usage.csv``. Target milestone: B.
"""

from __future__ import annotations

from pathlib import Path


def run_query(
    sql: str,
    *,
    project: str,
    location: str = "US",
    max_bytes: int,
    usage_report: Path = Path("reports/query_usage.csv"),
) -> Path:
    """Run one guarded query and return the path of the exported local result."""
    raise NotImplementedError("Milestone B implements BigQuery discovery execution.")


def render_sql_template(template_path: Path, parameters: dict[str, str]) -> str:
    """Render a parameterized SQL template from ``sql/`` with validated substitutions."""
    raise NotImplementedError("Milestone B implements SQL template rendering.")
