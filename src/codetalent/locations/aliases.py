"""Curated alias and manual-override application (spec section 15 steps 3-4).

Applies ``config/location_overrides.csv`` (each row carries documented
evidence) and ``config/location_aliases.csv`` before any parsing heuristics.
Target milestone: D.
"""

from __future__ import annotations

from codetalent.config import LocationAlias, LocationOverride
from codetalent.schemas import NormalizedLocation


def apply_override(
    actor_login: str, cleaned_location: str, overrides: list[LocationOverride]
) -> NormalizedLocation | None:
    """Return an override-based record, or None when no override matches."""
    raise NotImplementedError("Milestone D implements manual overrides.")


def apply_alias(
    actor_login: str, cleaned_location: str, aliases: list[LocationAlias]
) -> NormalizedLocation | None:
    """Return an alias-based record, or None when no alias matches."""
    raise NotImplementedError("Milestone D implements alias matching.")
