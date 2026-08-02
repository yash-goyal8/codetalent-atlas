"""Deterministic rule primitives for taxonomy classification (spec section 12).

Transparent weighted rules over repository topics, description and name terms,
primary language, and enrichment content signals. No LLM involvement; the same
inputs always produce the same outputs.

Matching semantics
------------------

* **Topics** match exactly after normalization: lowercase, with runs of
  hyphens, underscores, spaces, dots, and slashes collapsed to a single
  hyphen. ``Infrastructure_As_Code`` therefore matches the taxonomy topic
  ``infrastructure-as-code``, but ``terraforming-mars`` never matches
  ``terraform`` (no substring matching).
* **Terms** match as whole words or phrases inside lowercased text. A term
  like ``iac`` must not match inside ``maniac``; multi-word terms match as
  phrases whose words may be separated by spaces, hyphens, underscores, dots,
  or slashes (``infrastructure as code`` matches ``infrastructure-as-code``).
* **Negative terms** use the same phrase matching over the combined haystack
  of repository short name, description, and topics.
* **Content signals** (spec 9.2 booleans such as ``has_ci``) count as weak
  file evidence for the subdomains that declare them in their taxonomy
  ``content_signals`` list. Spec 9.2 metadata carries only these booleans, so
  the taxonomy's ``positive_files`` path lists are documentation for the
  manual-review rubric, never a classifier input (see
  :class:`codetalent.config.SubdomainTaxonomy`).
* **Primary language** contributes a weak hint for languages the taxonomy
  declares as domain-defining in ``language_hints`` (e.g. HCL for
  Infrastructure as Code), compared after topic-style normalization.

Weights come exclusively from ``config/scoring.yaml`` (``classification:``
block) and signal/language support exclusively from the taxonomy YAML; no
scoring number or taxonomy fact lives in this module.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from codetalent.classify.evidence import SubdomainEvidence
from codetalent.config import ClassificationConfig, SubdomainTaxonomy
from codetalent.schemas import RepositoryMetadata

_SEPARATOR_RUN = re.compile(r"[\s\-_./]+")


def normalize_token(raw: str) -> str:
    """Lowercase and collapse separator runs to single hyphens (topic form)."""
    return _SEPARATOR_RUN.sub("-", raw.strip().lower()).strip("-")


def repo_short_name(repo_name: str) -> str:
    """Return the repository name without its owner prefix."""
    return repo_name.split("/", 1)[-1]


@lru_cache(maxsize=8192)
def term_pattern(term: str) -> re.Pattern[str]:
    """Compile a word-boundary phrase pattern for one taxonomy term.

    Words in the term may be separated in the text by spaces, hyphens,
    underscores, dots, or slashes. Lookarounds forbid alphanumeric characters
    directly before or after the phrase so short terms never match inside
    unrelated words.
    """
    words = [word for word in _SEPARATOR_RUN.split(term.strip().lower()) if word]
    if not words:
        return re.compile(r"(?!)")  # a term with no words matches nothing
    body = r"[\s\-_./]+".join(re.escape(word) for word in words)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


def match_topics(repo_topics: Iterable[str], taxonomy_topics: Iterable[str]) -> tuple[str, ...]:
    """Return taxonomy topics exactly matched (post-normalization) by the repo."""
    normalized_repo = {normalize_token(topic) for topic in repo_topics}
    return tuple(
        sorted(topic for topic in taxonomy_topics if normalize_token(topic) in normalized_repo)
    )


def match_terms(text: str | None, terms: Iterable[str]) -> tuple[str, ...]:
    """Return the terms found in ``text`` with word-boundary phrase matching."""
    if not text:
        return ()
    haystack = text.lower()
    return tuple(sorted(term for term in terms if term_pattern(term).search(haystack)))


def negative_haystack(metadata: RepositoryMetadata) -> str:
    """Combined text negative terms scan: short name, description, and topics."""
    parts = [repo_short_name(metadata.repo_name), metadata.description or "", *metadata.topics]
    return " ".join(parts)


def content_signal_files(
    metadata: RepositoryMetadata, taxonomy: SubdomainTaxonomy
) -> tuple[str, ...]:
    """Spec 9.2 content signals declared by this subdomain that are True."""
    return tuple(
        sorted(
            signal for signal in set(taxonomy.content_signals) if getattr(metadata, signal) is True
        )
    )


def language_hints(metadata: RepositoryMetadata, taxonomy: SubdomainTaxonomy) -> tuple[str, ...]:
    """Normalized primary-language hint declared by this subdomain, if matched."""
    if metadata.primary_language is None:
        return ()
    normalized = normalize_token(metadata.primary_language)
    if normalized in {normalize_token(hint) for hint in taxonomy.language_hints}:
        return (normalized,)
    return ()


def evaluate_subdomain(
    subdomain_id: str,
    taxonomy: SubdomainTaxonomy,
    metadata: RepositoryMetadata,
    weights: ClassificationConfig,
) -> tuple[float, SubdomainEvidence]:
    """Score one repository against one subdomain and record the evidence.

    The score is the weighted sum of matched positive evidence minus weighted
    negative evidence. Distinct evidence kinds contribute additively, so a
    repository backed by several kinds of evidence compounds to a higher score
    than one backed by a single kind.
    """
    short_name = repo_short_name(metadata.repo_name)
    evidence = SubdomainEvidence(
        subdomain_id=subdomain_id,
        topics=match_topics(metadata.topics, taxonomy.positive_topics),
        description_terms=match_terms(metadata.description, taxonomy.positive_terms),
        name_terms=match_terms(short_name, taxonomy.positive_terms),
        files=content_signal_files(metadata, taxonomy),
        languages=language_hints(metadata, taxonomy),
        negative_terms=match_terms(negative_haystack(metadata), taxonomy.negative_terms),
    )
    score = (
        weights.topic_weight * len(evidence.topics)
        + weights.term_weight * len(evidence.description_terms)
        + weights.name_weight * len(evidence.name_terms)
        + weights.file_weight * len(evidence.files)
        + weights.language_weight * len(evidence.languages)
        - weights.negative_weight * len(evidence.negative_terms)
    )
    return score, evidence
