"""Location confidence assignment (spec section 15 confidence rules).

Maps each normalization outcome to high/medium/low/unusable per the spec:
only high+medium country matches enter country rankings, only high-confidence
city matches enter city rankings. Target milestone: D.
"""

from __future__ import annotations

from codetalent.schemas import LocationConfidence, NormalizationMethod


def assign_confidence(
    method: NormalizationMethod, *, ambiguous: bool, has_country: bool, has_city: bool
) -> LocationConfidence:
    """Return the confidence level for one normalization outcome."""
    raise NotImplementedError("Milestone D implements confidence assignment.")
