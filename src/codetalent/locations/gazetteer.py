"""Offline gazetteer built from pycountry, country_converter, and geonamescache.

Provides country and city lookups plus city-ambiguity detection using only
free offline datasets (spec 5.4). Target milestone: D.
"""

from __future__ import annotations


class Gazetteer:
    """In-memory country/city lookup tables built from offline sources."""

    def __init__(self) -> None:
        raise NotImplementedError("Milestone D implements the offline gazetteer.")

    def country_code_for(self, text: str) -> str | None:
        """Resolve a country name, ISO code, or common variant to ISO alpha-2."""
        raise NotImplementedError("Milestone D implements country resolution.")

    def city_candidates(self, text: str) -> list[tuple[str, str]]:
        """Return (city, country_code) candidates for a city string."""
        raise NotImplementedError("Milestone D implements city candidate lookup.")
