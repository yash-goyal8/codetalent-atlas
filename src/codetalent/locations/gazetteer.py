"""Offline gazetteer built from pycountry, country_converter, and geonamescache.

Provides country and city lookups plus city-ambiguity detection using only
free offline datasets (spec 5.4). No network access, ever. Lookup tables are
built once per process and iterated in sorted order so results are
deterministic across runs.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import country_converter as coco
import geonamescache
import pycountry

# country_converter logs a warning per unmatched lookup; unresolved strings
# are an expected, counted outcome here, not a problem worth log noise.
logging.getLogger("country_converter").setLevel(logging.ERROR)

# City-dominance rule (spec 15 step 7, documented in decisions.md): a lone city
# name is "globally recognizable" when the largest candidate has at least
# DOMINANT_MIN_POPULATION residents and is at least DOMINANT_RATIO times the
# size of the runner-up.
DOMINANT_MIN_POPULATION = 100_000
DOMINANT_RATIO = 5.0

# Non-US state/province/region names and abbreviations -> country. US states
# come from geonamescache; this curated table covers common non-US forms seen
# in GitHub locations.
REGION_TO_COUNTRY: dict[str, str] = {
    # Canada
    "on": "CA",
    "ontario": "CA",
    "bc": "CA",
    "british columbia": "CA",
    "qc": "CA",
    "quebec": "CA",
    "ab": "CA",
    "alberta": "CA",
    "manitoba": "CA",
    "nova scotia": "CA",
    "saskatchewan": "CA",
    # Australia
    "nsw": "AU",
    "new south wales": "AU",
    "vic": "AU",
    "victoria": "AU",
    "qld": "AU",
    "queensland": "AU",
    "tasmania": "AU",
    "act": "AU",
    # India
    "karnataka": "IN",
    "maharashtra": "IN",
    "tamil nadu": "IN",
    "telangana": "IN",
    "kerala": "IN",
    "west bengal": "IN",
    "delhi ncr": "IN",
    "uttar pradesh": "IN",
    "gujarat": "IN",
    "rajasthan": "IN",
    "haryana": "IN",
    "punjab": "IN",
    # Germany
    "bavaria": "DE",
    "bayern": "DE",
    "nrw": "DE",
    "north rhine-westphalia": "DE",
    "baden-wurttemberg": "DE",
    "baden-wuerttemberg": "DE",
    "hessen": "DE",
    "saxony": "DE",
    # UK constituents (country-level GB)
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    # Brazil
    "minas gerais": "BR",
    "rio grande do sul": "BR",
    # Misc frequent
    "catalonia": "ES",
    "catalunya": "ES",
    "andalusia": "ES",
    "bretagne": "FR",
    "ile-de-france": "FR",
    "occitanie": "FR",
    "lombardy": "IT",
    "lombardia": "IT",
    "tuscany": "IT",
    "toscana": "IT",
    "sindh": "PK",
}


def normalize_key(text: str) -> str:
    """Casefolded, diacritic-stripped, whitespace-collapsed matching key."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


@dataclass(frozen=True)
class CityRecord:
    """One gazetteer city entry."""

    name: str
    country_code: str
    admin1: str
    population: int
    latitude: float
    longitude: float


class Gazetteer:
    """In-memory country/city lookup tables built from offline sources."""

    def __init__(self) -> None:
        self._country_by_key: dict[str, str] = {}
        self._country_name_by_code: dict[str, str] = {}
        self._cities_by_key: dict[str, list[CityRecord]] = {}
        self._us_states: dict[str, str] = {}
        self._build_countries()
        self._build_cities()
        self._build_regions()

    # -- construction --------------------------------------------------------

    def _build_countries(self) -> None:
        for country in sorted(pycountry.countries, key=lambda c: c.alpha_2):
            code = country.alpha_2
            self._country_name_by_code[code] = country.name
            keys = {country.name, country.alpha_2, country.alpha_3}
            official = getattr(country, "official_name", None)
            if official:
                keys.add(official)
            common = getattr(country, "common_name", None)
            if common:
                keys.add(common)
            for key in keys:
                self._country_by_key.setdefault(normalize_key(key), code)
        # High-frequency informal forms not covered by pycountry's names.
        informal = {
            "usa": "US",
            "america": "US",
            "united states of america": "US",
            "uk": "GB",
            "great britain": "GB",
            "britain": "GB",
            "south korea": "KR",
            "north korea": "KP",
            "russia": "RU",
            "vietnam": "VN",
            "iran": "IR",
            "syria": "SY",
            "laos": "LA",
            "bolivia": "BO",
            "venezuela": "VE",
            "tanzania": "TZ",
            "moldova": "MD",
            "taiwan": "TW",
            "czechia": "CZ",
            "czech republic": "CZ",
            "turkey": "TR",
            "turkiye": "TR",
        }
        for name, code in informal.items():
            self._country_by_key.setdefault(normalize_key(name), code)

    def _build_cities(self) -> None:
        cache = geonamescache.GeonamesCache()
        for _, city in sorted(cache.get_cities().items()):
            record = CityRecord(
                name=city["name"],
                country_code=city["countrycode"],
                admin1=str(city.get("admin1code") or ""),
                population=int(city.get("population") or 0),
                latitude=float(city["latitude"]),
                longitude=float(city["longitude"]),
            )
            keys = {normalize_key(city["name"])}
            for alt in city.get("alternatenames") or []:
                # Short alternate names are noise in Latin script but real in
                # CJK and similar scripts (東京 is two characters).
                if alt and (len(alt) >= 3 or any(ord(ch) > 0x2E7F for ch in alt)):
                    keys.add(normalize_key(alt))
            for key in keys:
                if key:
                    self._cities_by_key.setdefault(key, []).append(record)
        for records in self._cities_by_key.values():
            records.sort(key=lambda r: (-r.population, r.country_code, r.name))

    def _build_regions(self) -> None:
        cache = geonamescache.GeonamesCache()
        for code, state in sorted(cache.get_us_states().items()):
            self._us_states[normalize_key(code)] = code
            self._us_states[normalize_key(state["name"])] = code

    # -- lookups -------------------------------------------------------------

    def country_code_for(self, text: str) -> str | None:
        """Resolve a country name, ISO code, or common variant to ISO alpha-2."""
        key = normalize_key(text)
        if not key:
            return None
        direct = self._country_by_key.get(key)
        if direct is not None:
            return direct
        # Only try the (slow, regex-based) converter for plausible names.
        if len(key) < 4:
            return None
        return _coco_lookup(key)

    def country_name_for(self, code: str) -> str | None:
        return self._country_name_by_code.get(code)

    def city_candidates(self, text: str, *, country_code: str | None = None) -> list[CityRecord]:
        """City candidates for a string, largest population first."""
        records = self._cities_by_key.get(normalize_key(text), [])
        if country_code is None:
            return list(records)
        return [r for r in records if r.country_code == country_code]

    def dominant_city(self, text: str) -> tuple[CityRecord | None, bool]:
        """(dominant record or None, ambiguous?) per the documented rule."""
        candidates = self.city_candidates(text)
        if not candidates:
            return None, False
        top = candidates[0]
        if top.population < DOMINANT_MIN_POPULATION:
            return None, True
        if len(candidates) == 1:
            return top, False
        runner_up = candidates[1].population
        if runner_up <= 0 or top.population >= DOMINANT_RATIO * runner_up:
            return top, False
        return None, True

    def us_state_code(self, text: str) -> str | None:
        return self._us_states.get(normalize_key(text))

    def region_country(self, text: str) -> str | None:
        """Country for a bare region/state/province string, if recognized."""
        if self.us_state_code(text) is not None:
            return "US"
        return REGION_TO_COUNTRY.get(normalize_key(text))


@lru_cache(maxsize=4096)
def _coco_lookup(key: str) -> str | None:
    """country_converter fallback for native/vernacular country names."""
    result = coco.convert(names=[key], to="ISO2", not_found=None)
    value = result[0] if isinstance(result, list) else result
    return value if isinstance(value, str) and len(value) == 2 else None


_SHARED: Gazetteer | None = None


def shared_gazetteer() -> Gazetteer:
    """Process-wide gazetteer (construction costs ~1s; reuse it)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = Gazetteer()
    return _SHARED
