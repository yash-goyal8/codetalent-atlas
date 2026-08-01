"""Weighted classification rules and accept/reject/borderline thresholds.

Rule weights and status thresholds live in configuration, never only in code.
Target milestone: C.
"""

from __future__ import annotations

from codetalent.config import SubdomainTaxonomy
from codetalent.schemas import RepositoryMetadata


def score_subdomain_match(metadata: RepositoryMetadata, taxonomy: SubdomainTaxonomy) -> float:
    """Return the weighted match score of one repository against one subdomain."""
    raise NotImplementedError("Milestone C implements subdomain rule scoring.")
