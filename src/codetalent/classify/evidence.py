"""Classification evidence records (spec 9.3, 28: evidence required for every decision).

Each repository-subdomain evaluation produces one :class:`SubdomainEvidence`
listing exactly which topics, description terms, name terms, file/content
signals, and language hints matched, plus every matched negative term. The
per-subdomain records are merged into the flat ``evidence_topics`` /
``evidence_terms`` / ``evidence_files`` / ``negative_evidence`` lists that the
spec 9.3 ``RepositoryClassification`` schema requires.

Evidence strings are self-describing so a reviewer can audit any decision:

* topics appear as the taxonomy topic that matched (e.g. ``terraform``);
* description terms appear verbatim (e.g. ``infrastructure as code``);
* name-term matches are prefixed ``name:`` (e.g. ``name:terraform``);
* language hints are prefixed ``language:`` (e.g. ``language:hcl``);
* file/content signals appear as the signal name (e.g. ``has_ci``);
* negative-term matches are prefixed ``negative_term:``; hard exclusions are
  prefixed ``exclusion:`` (added by the repository classifier).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

NAME_EVIDENCE_PREFIX = "name:"
LANGUAGE_EVIDENCE_PREFIX = "language:"
NEGATIVE_TERM_PREFIX = "negative_term:"


@dataclass(frozen=True)
class SubdomainEvidence:
    """Matched positive and negative signals for one repository-subdomain pair."""

    subdomain_id: str
    topics: tuple[str, ...] = ()
    description_terms: tuple[str, ...] = ()
    name_terms: tuple[str, ...] = ()
    files: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    negative_terms: tuple[str, ...] = ()

    @property
    def evidence_kinds(self) -> int:
        """Number of distinct positive evidence kinds present (0-5)."""
        groups = (
            self.topics,
            self.description_terms,
            self.name_terms,
            self.files,
            self.languages,
        )
        return sum(1 for group in groups if group)

    @property
    def has_positive_evidence(self) -> bool:
        return self.evidence_kinds > 0

    @property
    def has_any_evidence(self) -> bool:
        return self.has_positive_evidence or bool(self.negative_terms)


@dataclass(frozen=True)
class FlatEvidence:
    """Spec 9.3 flat evidence lists, deduplicated and sorted for determinism."""

    evidence_topics: list[str]
    evidence_terms: list[str]
    evidence_files: list[str]
    negative_evidence: list[str]


def merge_evidence(evidences: Iterable[SubdomainEvidence]) -> FlatEvidence:
    """Merge per-subdomain evidence into the spec 9.3 flat lists.

    Name-term and language evidence land in ``evidence_terms`` with their
    audit prefixes; negative-term matches land in ``negative_evidence`` with
    the ``negative_term:`` prefix. Output lists are sorted and deduplicated so
    identical inputs always produce identical records.
    """
    topics: set[str] = set()
    terms: set[str] = set()
    files: set[str] = set()
    negative: set[str] = set()
    for evidence in evidences:
        topics.update(evidence.topics)
        terms.update(evidence.description_terms)
        terms.update(f"{NAME_EVIDENCE_PREFIX}{term}" for term in evidence.name_terms)
        terms.update(f"{LANGUAGE_EVIDENCE_PREFIX}{lang}" for lang in evidence.languages)
        files.update(evidence.files)
        negative.update(f"{NEGATIVE_TERM_PREFIX}{term}" for term in evidence.negative_terms)
    return FlatEvidence(
        evidence_topics=sorted(topics),
        evidence_terms=sorted(terms),
        evidence_files=sorted(files),
        negative_evidence=sorted(negative),
    )
