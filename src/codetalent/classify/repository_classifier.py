"""Rule-based repository classifier producing spec 9.3 records (spec section 12).

Combines per-subdomain rule scores into one domain-level decision:

* ``classification_score`` is the **maximum** subdomain score (documented
  choice: the max keeps the score interpretable as "strength of the best
  subdomain match"; a soft-max would blur evidence across subdomains),
  clipped into the spec 9.3 ``[0, 100]`` range.
* ``subdomains`` lists every subdomain meeting the acceptance criteria
  (score >= accept_threshold and >= min_evidence_kinds distinct evidence
  kinds), or — for borderline repositories — every subdomain at or above the
  borderline threshold, ordered by descending score then subdomain id.
* ``classification_status`` is ``accepted`` / ``borderline`` / ``rejected``
  from the configured thresholds.

Spec 12 exclusion rules are hard overrides applied before any scoring: a
matching repository is rejected with ``exclusion:<reason>`` entries in
``negative_evidence``, a score of 0.0, and no subdomains, regardless of how
much positive evidence exists. Every requirement and exclusion check is gated
on its ``config/repo_filters.yaml`` flag (spec 8.2), so turning a flag off in
configuration really disables the corresponding check.

Known spec 8.2 gaps, deliberate and documented:

* ``requirements.must_be_public`` — everything reaching this classifier was
  fetched through the public GitHub API, so it is public by construction.
* ``requirements.require_recent_activity`` and the activity minimums — already
  enforced upstream by BigQuery discovery (the worklist is
  ``discovery_status == "accepted"`` only).
* ``exclusions.mirrors`` and ``exclusions.generated_copies`` — spec 9.2
  metadata has no ``is_mirror`` field and no generated-copy signal, so these
  flags are currently unenforceable here; they are accepted in configuration
  for the spec 8.2 contract but produce no check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from codetalent.classify.evidence import SubdomainEvidence, merge_evidence
from codetalent.classify.rules import evaluate_subdomain, repo_short_name
from codetalent.config import (
    ClassificationConfig,
    FilterExclusions,
    RepoFiltersConfig,
    TaxonomyConfig,
)
from codetalent.schemas import ClassificationStatus, RepositoryClassification, RepositoryMetadata

EXCLUSION_PREFIX = "exclusion:"

_MAX_SCORE = 100.0

# Recognized open-source licenses (spec 12 inclusion rule), as GitHub SPDX
# ids. OSI-approved or OSI-equivalent free licenses only. ``NOASSERTION``
# (GitHub's marker for a custom/unrecognized license file) is deliberately
# NOT recognized, and neither is a missing license. This is a fixed data
# constant (which licenses exist and are open source), not a tunable weight,
# so it lives in source; the *decision* to require a recognized license is
# configuration (``requirements.require_recognized_license``).
RECOGNIZED_LICENSE_SPDX_IDS: frozenset[str] = frozenset(
    {
        "0BSD",
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "Apache-2.0",
        "Artistic-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "BSD-3-Clause-Clear",
        "BSL-1.0",
        "CC0-1.0",
        "EPL-1.0",
        "EPL-2.0",
        "EUPL-1.2",
        "GPL-2.0",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
        "GPL-3.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
        "ISC",
        "LGPL-2.1",
        "LGPL-2.1-only",
        "LGPL-2.1-or-later",
        "LGPL-3.0",
        "LGPL-3.0-only",
        "LGPL-3.0-or-later",
        "MIT",
        "MPL-2.0",
        "MulanPSL-2.0",
        "PostgreSQL",
        "Unlicense",
        "Zlib",
    }
)
_RECOGNIZED_LICENSES_UPPER = frozenset(spdx.upper() for spdx in RECOGNIZED_LICENSE_SPDX_IDS)

# Spec 12 exclusion patterns over the repository short name (lowercased).
# Conservative by design: e.g. only an exact "docs"/"documentation" name is
# documentation-only, so real tools like terraform-docs are not excluded.
_NAME_EXCLUSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("awesome_list", re.compile(r"^awesome([-_].+)?$|[-_]awesome$")),
    ("tutorial", re.compile(r"(^|[-_])tutorials?($|[-_])|^learn(ing)?[-_]")),
    ("interview_prep", re.compile(r"interview|leetcode")),
    ("dotfiles", re.compile(r"(^|[-_.])dotfiles?($|[-_])")),
    # Course codes such as cse110, swp391, comp3120 (2-5 letters + 3-4
    # digits). Two guards keep real engineering names out of this net:
    # a negative lookahead for well-known letters+digits prefixes (cve-2021-*,
    # rfc-3339-*, es2015-*, sha256-*, ...) and a requirement that the digit
    # group is not followed by another digit group (cve-2021-44228 style ids
    # are never course codes).
    (
        "student_assignment",
        re.compile(
            r"^(?!(?:cve|rfc|iso|ieee|ecma|es|sha|aes|utf)[-_]?\d)"
            r"[a-z]{2,5}[-_]?\d{3,4}(?:$|[-_](?!\d))"
        ),
    ),
    ("documentation_only", re.compile(r"^(docs?|documentation|handbook|wiki)$")),
)

# Spec 12 exclusion patterns over the description (lowercased).
_DESCRIPTION_EXCLUSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("awesome_list", re.compile(r"\b(awesome list|curated list)\b")),
    (
        "tutorial",
        re.compile(r"\b(tutorials?|for beginners|step[ -]by[ -]step guide|crash course)\b"),
    ),
    ("interview_prep", re.compile(r"\binterview (questions?|prep(aration)?)\b|\bleetcode\b")),
    ("dotfiles", re.compile(r"\bdotfiles\b")),
    (
        "student_assignment",
        re.compile(
            r"\b(homework|assignments?|coursework|course (project|work|assignment)"
            r"|university (course|project|assignment)|school project|capstone project"
            r"|semester)\b"
        ),
    ),
    ("documentation_only", re.compile(r"\b(documentation only|docs only)\b")),
)

# Pattern tag -> the config/repo_filters.yaml exclusion flag that enables it.
_EXCLUSION_TAG_FLAGS: dict[str, str] = {
    "awesome_list": "awesome_lists",
    "tutorial": "tutorial_only",
    "interview_prep": "interview_prep",
    "dotfiles": "dotfiles",
    "student_assignment": "student_assignments",
    "documentation_only": "documentation_only",
}


def _exclusion_enabled(exclusions: FilterExclusions, tag: str) -> bool:
    return bool(getattr(exclusions, _EXCLUSION_TAG_FLAGS[tag]))


@dataclass(frozen=True)
class SubdomainScore:
    """One subdomain's weighted rule score with its supporting evidence."""

    subdomain_id: str
    score: float
    evidence: SubdomainEvidence


def license_is_recognized(license_spdx_id: str | None) -> bool:
    """True when the SPDX id is on the recognized open-source list."""
    if license_spdx_id is None:
        return False
    return license_spdx_id.upper() in _RECOGNIZED_LICENSES_UPPER


def hard_exclusion_reasons(
    metadata: RepositoryMetadata,
    *,
    filters: RepoFiltersConfig,
    single_actor_event_share: float | None,
) -> list[str]:
    """All spec 12 hard-exclusion reasons that apply, as ``exclusion:<tag>`` strings.

    Every check runs only when its ``config/repo_filters.yaml`` flag enables
    it (spec 8.2); the dominance threshold likewise comes from
    ``exclusions.single_contributor_dominance_threshold``. Ordering is fixed
    (metadata flags, license, dominance, then name and description patterns)
    so identical inputs yield identical reason lists.
    """
    requirements = filters.requirements
    exclusions = filters.exclusions
    reasons: list[str] = []
    if requirements.must_not_be_fork and metadata.is_fork:
        reasons.append("fork")
    if requirements.must_not_be_archived and metadata.is_archived:
        reasons.append("archived")
    if requirements.must_not_be_disabled and metadata.is_disabled:
        reasons.append("disabled")
    if requirements.require_recognized_license and not license_is_recognized(
        metadata.license_spdx_id
    ):
        reasons.append("license")
    if (
        single_actor_event_share is not None
        and single_actor_event_share > exclusions.single_contributor_dominance_threshold
    ):
        reasons.append("single_actor_dominance")

    short_name = repo_short_name(metadata.repo_name).lower()
    description = (metadata.description or "").lower()
    for tag, pattern in _NAME_EXCLUSION_PATTERNS:
        if (
            tag not in reasons
            and _exclusion_enabled(exclusions, tag)
            and pattern.search(short_name)
        ):
            reasons.append(tag)
    for tag, pattern in _DESCRIPTION_EXCLUSION_PATTERNS:
        if (
            tag not in reasons
            and _exclusion_enabled(exclusions, tag)
            and pattern.search(description)
        ):
            reasons.append(tag)
    return [f"{EXCLUSION_PREFIX}{tag}" for tag in reasons]


def score_subdomains(
    metadata: RepositoryMetadata,
    taxonomy: TaxonomyConfig,
    weights: ClassificationConfig,
) -> list[SubdomainScore]:
    """Evaluate every subdomain of the taxonomy against one repository."""
    scored: list[SubdomainScore] = []
    for subdomain_id, subdomain in taxonomy.subdomains.items():
        score, evidence = evaluate_subdomain(subdomain_id, subdomain, metadata, weights)
        scored.append(SubdomainScore(subdomain_id=subdomain_id, score=score, evidence=evidence))
    return scored


def _clip_score(score: float) -> float:
    return min(max(score, 0.0), _MAX_SCORE)


def classify_repository(
    metadata: RepositoryMetadata,
    taxonomy: TaxonomyConfig,
    weights: ClassificationConfig,
    *,
    filters: RepoFiltersConfig,
    single_actor_event_share: float | None,
) -> RepositoryClassification:
    """Classify one repository against a domain taxonomy with recorded evidence.

    ``single_actor_event_share`` comes from the spec 9.1 activity summary
    (``None`` when the repository has no activity row); ``filters`` is the
    spec 8.2 ``config/repo_filters.yaml`` contract gating every requirement
    and exclusion check.
    """
    exclusions = hard_exclusion_reasons(
        metadata,
        filters=filters,
        single_actor_event_share=single_actor_event_share,
    )
    if exclusions:
        return RepositoryClassification(
            repo_name=metadata.repo_name,
            domain_id=taxonomy.domain_id,
            subdomains=[],
            classification_score=0.0,
            classification_status=ClassificationStatus.REJECTED,
            evidence_topics=[],
            evidence_terms=[],
            evidence_files=[],
            negative_evidence=exclusions,
            manual_label=None,
            manual_notes=None,
        )

    scored = score_subdomains(metadata, taxonomy, weights)

    accepted = [
        entry
        for entry in scored
        if entry.score >= weights.accept_threshold
        and entry.evidence.evidence_kinds >= weights.min_evidence_kinds
    ]
    if accepted:
        status = ClassificationStatus.ACCEPTED
        chosen = accepted
    else:
        borderline = [entry for entry in scored if entry.score >= weights.borderline_threshold]
        if borderline:
            status = ClassificationStatus.BORDERLINE
            chosen = borderline
        else:
            status = ClassificationStatus.REJECTED
            chosen = []

    chosen = sorted(chosen, key=lambda entry: (-entry.score, entry.subdomain_id))
    # Evidence transparency: accepted/borderline records carry the evidence of
    # their listed subdomains; rejected records carry whatever weak or negative
    # evidence existed anywhere, so manual review can see why the score fell short.
    evidence_sources = chosen if chosen else [s for s in scored if s.evidence.has_any_evidence]
    flat = merge_evidence(entry.evidence for entry in evidence_sources)

    # Auditability: an accepted/borderline record's score is the best score
    # among its *listed* subdomains, so the score is always explainable from
    # the recorded evidence. A subdomain that failed the evidence gate never
    # drives the score of a record it is not listed on. Rejected records keep
    # the overall best score so review can see how close the repository came.
    best_score = chosen[0].score if chosen else max((entry.score for entry in scored), default=0.0)

    return RepositoryClassification(
        repo_name=metadata.repo_name,
        domain_id=taxonomy.domain_id,
        subdomains=[entry.subdomain_id for entry in chosen],
        classification_score=_clip_score(best_score),
        classification_status=status,
        evidence_topics=flat.evidence_topics,
        evidence_terms=flat.evidence_terms,
        evidence_files=flat.evidence_files,
        negative_evidence=flat.negative_evidence,
        manual_label=None,
        manual_notes=None,
    )
