"""Location confidence assignment (spec section 15 confidence rules).

The pipeline computes most confidences at the resolution site (the outcome —
curated pair vs heuristic pick — determines the tier, not just the method).
This module centralizes the spec mapping used there plus the aggregation
eligibility rules: country rankings admit high+medium country matches; city
rankings admit high-confidence city matches only; low-confidence rows appear
only in coverage diagnostics.
"""

from __future__ import annotations

from codetalent.schemas import LocationConfidence, LocationLevel, NormalizedLocation


def country_ranking_eligible(row: NormalizedLocation) -> bool:
    """Spec 15: high and medium country matches enter country rankings."""
    return row.normalized_country_code is not None and row.location_confidence in (
        LocationConfidence.HIGH,
        LocationConfidence.MEDIUM,
    )


def city_ranking_eligible(row: NormalizedLocation) -> bool:
    """Spec 15: only high-confidence city matches enter city rankings."""
    return (
        row.normalized_city is not None
        and row.location_level is LocationLevel.CITY
        and row.location_confidence is LocationConfidence.HIGH
    )
