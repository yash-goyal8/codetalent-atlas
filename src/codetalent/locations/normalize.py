"""Location normalization pipeline (spec section 15).

Applies the ordered steps: placeholder removal, unicode cleanup, manual
override, exact alias, country match, city-country pair, unique city,
region+country, ambiguity detection, unresolved output. Target milestone: D.
"""

from __future__ import annotations

from codetalent.config import LocationAlias, LocationOverride
from codetalent.schemas import NormalizedLocation


def normalize_location(
    actor_login: str,
    raw_location: str | None,
    *,
    aliases: list[LocationAlias],
    overrides: list[LocationOverride],
) -> NormalizedLocation:
    """Normalize one free-form public location into a spec 9.6 record."""
    raise NotImplementedError("Milestone D implements location normalization.")
