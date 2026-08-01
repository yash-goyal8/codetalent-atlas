"""Rule-based repository classifier producing spec 9.3 records.

Applies transparent weighted rules over topics, description/name terms,
primary language, domain files, and negative evidence. No LLM involvement.
Target milestone: C.
"""

from __future__ import annotations

from codetalent.config import TaxonomyConfig
from codetalent.schemas import RepositoryClassification, RepositoryMetadata


def classify_repository(
    metadata: RepositoryMetadata, taxonomy: TaxonomyConfig
) -> RepositoryClassification:
    """Classify one repository against a domain taxonomy with recorded evidence."""
    raise NotImplementedError("Milestone C implements repository classification.")
