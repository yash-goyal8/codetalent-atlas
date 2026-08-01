"""Repository quality score (spec 16.1): 0-100 from configured component weights.

30% recent activity + 25% contributor diversity + 20% collaboration quality
+ 15% technical relevance + 10% repository maturity, with robust scaling
(percentile ranks, log1p, winsorization) from ``config/scoring.yaml``.
Target milestone: E.
"""

from __future__ import annotations

from codetalent.config import ScoringConfig
from codetalent.schemas import (
    RepositoryActivitySummary,
    RepositoryClassification,
    RepositoryMetadata,
)


def score_repository(
    activity: RepositoryActivitySummary,
    metadata: RepositoryMetadata,
    classification: RepositoryClassification,
    config: ScoringConfig,
) -> float:
    """Return one repository's 0-100 quality score from configured weights."""
    raise NotImplementedError("Milestone E implements repository quality scoring.")
