"""BigQuery dry-run cost estimation (spec section 13: every query supports a dry run).

Estimates bytes processed before execution and fails when the estimate exceeds
the configured budget, per the failure policy "BigQuery dry-run over budget:
fail before execution". Target milestone: B.
"""

from __future__ import annotations


def estimate_query_bytes(sql: str, *, project: str, location: str = "US") -> int:
    """Return the dry-run estimate of bytes this query would process."""
    raise NotImplementedError("Milestone B implements the BigQuery dry-run estimator.")


def assert_within_budget(estimated_bytes: int, max_bytes: int) -> None:
    """Raise if the dry-run estimate exceeds the configured byte budget."""
    raise NotImplementedError("Milestone B implements the query budget guard.")
