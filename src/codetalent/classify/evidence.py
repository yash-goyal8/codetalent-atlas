"""Classification evidence extraction (spec 9.3, 28: evidence required for accepted records).

Collects the matched topics, terms, files, and negative signals that justify
every classification decision. Target milestone: C.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ClassificationEvidence:
    """Matched positive and negative signals for one repository-subdomain pair."""

    topics: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)


def collect_evidence(
    topics: list[str], description: str | None, repo_name: str, terms: list[str]
) -> ClassificationEvidence:
    """Extract matched evidence strings for auditable classification."""
    raise NotImplementedError("Milestone C implements evidence collection.")
