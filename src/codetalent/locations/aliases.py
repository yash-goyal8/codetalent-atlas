"""Curated alias and manual-override application (spec section 15 steps 3-4).

Applies ``config/location_overrides.csv`` (each row carries documented
evidence) and ``config/location_aliases.csv`` before any parsing heuristics —
earlier pipeline stages always win over later ones.
"""

from __future__ import annotations

from codetalent.config import LocationAlias, LocationOverride
from codetalent.locations.gazetteer import Gazetteer, normalize_key
from codetalent.schemas import (
    LocationConfidence,
    LocationLevel,
    NormalizationMethod,
    NormalizedLocation,
)


def _record(
    actor_login: str,
    raw_location: str,
    *,
    country_code: str,
    city: str | None,
    level: LocationLevel,
    method: NormalizationMethod,
    confidence: LocationConfidence,
    gazetteer: Gazetteer,
) -> NormalizedLocation:
    latitude = longitude = None
    if city is not None:
        for candidate in gazetteer.city_candidates(city, country_code=country_code):
            latitude, longitude = candidate.latitude, candidate.longitude
            break
    return NormalizedLocation(
        actor_login=actor_login,
        raw_location=raw_location,
        normalized_country_code=country_code,
        normalized_country_name=gazetteer.country_name_for(country_code),
        normalized_city=city,
        latitude=latitude,
        longitude=longitude,
        location_level=level,
        location_confidence=confidence,
        normalization_method=method,
    )


def apply_override(
    actor_login: str,
    raw_location: str,
    cleaned_location: str,
    overrides: list[LocationOverride],
    gazetteer: Gazetteer,
) -> NormalizedLocation | None:
    """Manual override (spec: high confidence, documented evidence)."""
    key = normalize_key(cleaned_location)
    for override in overrides:
        if normalize_key(override.raw_location) == key:
            return _record(
                actor_login,
                raw_location,
                country_code=override.normalized_country_code,
                city=override.normalized_city,
                level=override.location_level,
                method=NormalizationMethod.MANUAL_OVERRIDE,
                confidence=LocationConfidence.HIGH,
                gazetteer=gazetteer,
            )
    return None


def apply_alias(
    actor_login: str,
    raw_location: str,
    cleaned_location: str,
    aliases: list[LocationAlias],
    gazetteer: Gazetteer,
) -> NormalizedLocation | None:
    """Exact curated alias. City/country aliases are high confidence (spec:
    exact curated pair); region-level aliases are broad and therefore low."""
    key = normalize_key(cleaned_location)
    for alias in aliases:
        if normalize_key(alias.alias) == key:
            confidence = (
                LocationConfidence.LOW
                if alias.location_level is LocationLevel.REGION
                else LocationConfidence.HIGH
            )
            return _record(
                actor_login,
                raw_location,
                country_code=alias.normalized_country_code,
                city=alias.normalized_city,
                level=alias.location_level,
                method=NormalizationMethod.EXACT_ALIAS,
                confidence=confidence,
                gazetteer=gazetteer,
            )
    return None
