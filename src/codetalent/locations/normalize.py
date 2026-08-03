"""Location normalization pipeline (spec section 15, stages in its exact order).

Stage order: (1) null/placeholder removal, (2) unicode cleanup, (3) manual
override, (4) exact alias, (5) explicit country, (6) city-country pair,
(7) unique globally recognizable city, (8) region/state + country,
(9) ambiguity detection, (10) unresolved. Earlier stages always win.

Confidence interpretation (documented in decisions.md): a gazetteer-verified
city-country pair with a single in-country candidate is treated as the spec's
high-confidence "exact curated city-country pair"; same-name collisions within
the country demote to medium with an ambiguity reason. State/region + country
combinations are medium per the spec; lone dominant cities are medium; lone
ambiguous cities resolved heuristically are low; broad regions alone are low.
"""

from __future__ import annotations

import re
import unicodedata

from codetalent.config import LocationAlias, LocationOverride
from codetalent.locations.aliases import apply_alias, apply_override
from codetalent.locations.gazetteer import CityRecord, Gazetteer, shared_gazetteer
from codetalent.schemas import (
    LocationConfidence,
    LocationLevel,
    NormalizationMethod,
    NormalizedLocation,
)

# Spec 15 step 1: virtual/joke placeholders (matched on the cleaned casefold).
PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "earth",
        "planet earth",
        "mother earth",
        "internet",
        "the internet",
        "online",
        "remote",
        "worldwide",
        "world",
        "global",
        "everywhere",
        "somewhere",
        "nowhere",
        "localhost",
        "127.0.0.1",
        "the cloud",
        "cloud",
        "cyberspace",
        "metaverse",
        "the moon",
        "moon",
        "mars",
        "milky way",
        "universe",
        "the universe",
        "home",
        "my house",
        "behind you",
        "unknown",
        "n/a",
        "none",
        "null",
        "undefined",
    }
)

_MULTI_SEPARATORS = re.compile(r"\s*(?:/|\||•|·|;|&| and )\s*", re.IGNORECASE)


def _clean(text: str) -> str:
    """Stage 2: NFKC normalization, symbol/emoji stripping, whitespace collapse."""
    normalized = unicodedata.normalize("NFKC", text)
    kept: list[str] = []
    for ch in normalized:
        category = unicodedata.category(ch)
        if category.startswith(("So", "Sk", "Cs", "Co")):
            continue
        kept.append(ch)
    collapsed = " ".join("".join(kept).split())
    return collapsed.strip(" ,;-·|/")


def _unusable(actor_login: str, raw: str | None, reason: str | None = None) -> NormalizedLocation:
    return NormalizedLocation(
        actor_login=actor_login,
        raw_location=raw,
        location_level=LocationLevel.UNKNOWN,
        location_confidence=LocationConfidence.UNUSABLE,
        normalization_method=NormalizationMethod.UNRESOLVED,
        ambiguity_reason=reason,
    )


def _country_record(
    actor_login: str,
    raw: str,
    country_code: str,
    gazetteer: Gazetteer,
    *,
    level: LocationLevel = LocationLevel.COUNTRY,
    confidence: LocationConfidence = LocationConfidence.HIGH,
    reason: str | None = None,
) -> NormalizedLocation:
    return NormalizedLocation(
        actor_login=actor_login,
        raw_location=raw,
        normalized_country_code=country_code,
        normalized_country_name=gazetteer.country_name_for(country_code),
        location_level=level,
        location_confidence=confidence,
        normalization_method=NormalizationMethod.PARSED_COUNTRY,
        ambiguity_reason=reason,
    )


def _city_record(
    actor_login: str,
    raw: str,
    record: CityRecord,
    gazetteer: Gazetteer,
    *,
    method: NormalizationMethod,
    confidence: LocationConfidence,
    reason: str | None = None,
) -> NormalizedLocation:
    return NormalizedLocation(
        actor_login=actor_login,
        raw_location=raw,
        normalized_country_code=record.country_code,
        normalized_country_name=gazetteer.country_name_for(record.country_code),
        normalized_city=record.name,
        latitude=record.latitude,
        longitude=record.longitude,
        location_level=LocationLevel.CITY,
        location_confidence=confidence,
        normalization_method=method,
        ambiguity_reason=reason,
    )


def _resolve_city_in_country(
    actor_login: str,
    raw: str,
    city_text: str,
    country_code: str,
    gazetteer: Gazetteer,
    *,
    admin1: str | None = None,
    pair_confidence: LocationConfidence,
) -> NormalizedLocation | None:
    """Stage 6 helper: verify a city inside an anchored country."""
    candidates = gazetteer.city_candidates(city_text, country_code=country_code)
    if admin1 is not None:
        narrowed = [c for c in candidates if c.admin1 == admin1]
        candidates = narrowed or candidates
    if not candidates:
        return None
    if len(candidates) == 1:
        return _city_record(
            actor_login,
            raw,
            candidates[0],
            gazetteer,
            method=NormalizationMethod.CITY_COUNTRY_PAIR,
            confidence=pair_confidence,
        )
    return _city_record(
        actor_login,
        raw,
        candidates[0],
        gazetteer,
        method=NormalizationMethod.CITY_COUNTRY_PAIR,
        confidence=LocationConfidence.MEDIUM,
        reason=f"{len(candidates)} same-name cities in {country_code}; largest chosen",
    )


def _resolve_single_term(
    actor_login: str, raw: str, term: str, gazetteer: Gazetteer
) -> NormalizedLocation:
    """Stages 7-10 for a lone term: region, unique city, else unresolved.

    Regions are checked BEFORE city dominance: a bare US state or known region
    name ("Virginia", "Bavaria") is a region statement even when some city
    somewhere shares the name (the 500-string review caught "Virginia" mapping
    to a South African town). Cost: "New York" resolves as the state (region,
    correct country) rather than the city — the honest reading of a bare
    state-name string.
    """
    region_first = gazetteer.region_country(term)
    if region_first is not None:
        return _country_record(
            actor_login,
            raw,
            region_first,
            gazetteer,
            level=LocationLevel.REGION,
            confidence=LocationConfidence.LOW,
            reason="broad region only",
        )
    dominant, ambiguous = gazetteer.dominant_city(term)
    if dominant is not None:
        return _city_record(
            actor_login,
            raw,
            dominant,
            gazetteer,
            method=NormalizationMethod.UNIQUE_CITY,
            confidence=LocationConfidence.MEDIUM,
        )
    region_country = gazetteer.region_country(term)
    if region_country is not None:
        return _country_record(
            actor_login,
            raw,
            region_country,
            gazetteer,
            level=LocationLevel.REGION,
            confidence=LocationConfidence.LOW,
            reason="broad region only",
        )
    if ambiguous:
        candidates = gazetteer.city_candidates(term)
        top = candidates[0]
        return _city_record(
            actor_login,
            raw,
            top,
            gazetteer,
            method=NormalizationMethod.UNIQUE_CITY,
            confidence=LocationConfidence.LOW,
            reason=f"ambiguous city ({len(candidates)} candidates); largest chosen",
        )
    return _unusable(actor_login, raw, "unresolved text")


def normalize_location(
    actor_login: str,
    raw_location: str | None,
    *,
    aliases: list[LocationAlias],
    overrides: list[LocationOverride],
    gazetteer: Gazetteer | None = None,
) -> NormalizedLocation:
    """Normalize one free-form public location into a spec 9.6 record."""
    gaz = gazetteer if gazetteer is not None else shared_gazetteer()

    # Stage 1-2: null handling and cleanup.
    if raw_location is None or not raw_location.strip():
        return _unusable(actor_login, raw_location)
    cleaned = _clean(raw_location)
    if not cleaned:
        return _unusable(actor_login, raw_location, "emoji or symbols only")
    if cleaned.casefold() in PLACEHOLDERS:
        return _unusable(actor_login, raw_location, "virtual or joke location")

    # Stage 3: manual override.  Stage 4: exact alias.
    for stage in (apply_override, apply_alias):
        table = overrides if stage is apply_override else aliases
        result = stage(actor_login, raw_location, cleaned, table, gaz)  # type: ignore[arg-type]
        if result is not None:
            return result

    # Stage 5: explicit whole-string country. Only for comma-free strings —
    # "Berlin, Germany" must reach the pair stage, and country_converter's
    # regex fallback happily matches a country name inside a longer string.
    if "," not in cleaned:
        country = gaz.country_code_for(cleaned)
        if country is not None:
            if gaz.us_state_code(cleaned) is not None:
                # "Georgia": a country name that is also a US state — honest
                # ambiguity, never a confident country claim.
                return _country_record(
                    actor_login,
                    raw_location,
                    country,
                    gaz,
                    confidence=LocationConfidence.LOW,
                    reason="country name is also a US state name",
                )
            return _country_record(actor_login, raw_location, country, gaz)

    # Multiple-location strings ("London / Paris") conflict unless they agree.
    parts = [p for p in _MULTI_SEPARATORS.split(cleaned) if p]
    if len(parts) > 1:
        resolved = [
            normalize_location(
                actor_login, part, aliases=aliases, overrides=overrides, gazetteer=gaz
            )
            for part in parts
        ]
        countries = {r.normalized_country_code for r in resolved if r.normalized_country_code}
        if len(countries) > 1:
            return _unusable(actor_login, raw_location, "multiple conflicting locations")
        for candidate in resolved:
            if candidate.normalized_country_code is not None:
                return candidate.model_copy(update={"raw_location": raw_location})
        return _unusable(actor_login, raw_location, "unresolved text")

    segments = [s.strip() for s in cleaned.split(",") if s.strip()]

    if len(segments) >= 2:
        last = segments[-1]
        head = segments[0]

        # US-state-with-verified-city runs BEFORE the ISO-country anchor:
        # "Cambridge, MA" means Massachusetts, not Morocco, and the state
        # reading only wins when the city actually exists in that state —
        # "Munich, DE" finds no Munich in Delaware and falls through to
        # Germany below.
        state = gaz.us_state_code(last)
        if state is not None:
            state_pair = _resolve_city_in_country(
                actor_login,
                raw_location,
                head,
                "US",
                gaz,
                admin1=state,
                pair_confidence=LocationConfidence.MEDIUM,
            )
            if state_pair is not None and state_pair.normalized_city is not None:
                verified = any(
                    c.admin1 == state for c in gaz.city_candidates(head, country_code="US")
                )
                if verified:
                    return state_pair

        # Stage 6: city-country pair (country anchor in the last segment).
        anchor_country = gaz.country_code_for(last)
        if anchor_country is not None:
            if anchor_country == "US" and gaz.us_state_code(head) is not None:
                # "Maryland, USA" / "New York, USA": a US state name before a
                # US anchor is a region statement, not a city (the review
                # caught "Maryland" matching the town Maryland City).
                return _country_record(
                    actor_login,
                    raw_location,
                    "US",
                    gaz,
                    level=LocationLevel.REGION,
                    confidence=LocationConfidence.MEDIUM,
                )
            middle = segments[-2] if len(segments) >= 3 else None
            admin1 = (
                gaz.us_state_code(middle) if middle is not None and anchor_country == "US" else None
            )
            pair = _resolve_city_in_country(
                actor_login,
                raw_location,
                head,
                anchor_country,
                gaz,
                admin1=admin1,
                pair_confidence=LocationConfidence.HIGH,
            )
            if pair is not None:
                return pair
            region_of_anchor = gaz.region_country(head)
            if region_of_anchor == anchor_country:
                # "Ontario, Canada" — region + country combination (medium).
                return _country_record(
                    actor_login,
                    raw_location,
                    anchor_country,
                    gaz,
                    level=LocationLevel.REGION,
                    confidence=LocationConfidence.MEDIUM,
                )
            return _country_record(
                actor_login,
                raw_location,
                anchor_country,
                gaz,
                confidence=LocationConfidence.HIGH,
                reason="city segment not in gazetteer",
            )

        # Stage 8: region/state + city ("Austin, TX" / "Toronto, ON").
        state = gaz.us_state_code(last)
        if state is not None:
            pair = _resolve_city_in_country(
                actor_login,
                raw_location,
                head,
                "US",
                gaz,
                admin1=state,
                pair_confidence=LocationConfidence.MEDIUM,
            )
            if pair is not None:
                return pair
            return _country_record(
                actor_login,
                raw_location,
                "US",
                gaz,
                level=LocationLevel.REGION,
                confidence=LocationConfidence.MEDIUM,
                reason="state recognized; city not in gazetteer",
            )
        region_country = gaz.region_country(last)
        if region_country is not None:
            pair = _resolve_city_in_country(
                actor_login,
                raw_location,
                head,
                region_country,
                gaz,
                pair_confidence=LocationConfidence.MEDIUM,
            )
            if pair is not None:
                return pair
            return _country_record(
                actor_login,
                raw_location,
                region_country,
                gaz,
                level=LocationLevel.REGION,
                confidence=LocationConfidence.MEDIUM,
                reason="region recognized; city not in gazetteer",
            )

        # Stage 9: neither segment anchors a country — try the head alone.
        head_result = _resolve_single_term(actor_login, raw_location, head, gaz)
        if head_result.location_confidence is not LocationConfidence.UNUSABLE:
            return head_result
        return _unusable(actor_login, raw_location, "unresolved text")

    # Stages 7-10: single term.
    return _resolve_single_term(actor_login, raw_location, cleaned, gaz)
