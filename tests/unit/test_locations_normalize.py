"""Offline location-normalization tests (spec section 15). No network."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from codetalent.config import AtlasConfig, LocationAlias, LocationOverride, load_all
from codetalent.locations.confidence import city_ranking_eligible, country_ranking_eligible
from codetalent.locations.gazetteer import Gazetteer, shared_gazetteer
from codetalent.locations.normalize import normalize_location
from codetalent.locations.runner import normalize_profile_locations
from codetalent.schemas import (
    LocationConfidence,
    LocationLevel,
    NormalizationMethod,
    NormalizedLocation,
)


@pytest.fixture(scope="module")
def gazetteer() -> Gazetteer:
    return shared_gazetteer()


@pytest.fixture(scope="module")
def config() -> AtlasConfig:
    return load_all(Path(__file__).resolve().parents[2] / "config")


def run(config: AtlasConfig, gazetteer: Gazetteer, raw: str | None) -> NormalizedLocation:
    return normalize_location(
        "someone",
        raw,
        aliases=config.location_aliases,
        overrides=config.location_overrides,
        gazetteer=gazetteer,
    )


# (raw, country, city-or-None, level, confidence) — the golden behavior table.
GOLDEN: list[tuple[str, str | None, str | None, LocationLevel, LocationConfidence]] = [
    ("Germany", "DE", None, LocationLevel.COUNTRY, LocationConfidence.HIGH),
    ("FR", "FR", None, LocationLevel.COUNTRY, LocationConfidence.HIGH),
    # Bare codes that are ALSO US state codes (DE=Delaware, CA=California...)
    # are honestly ambiguous -> low, excluded from country rankings.
    ("DE", "DE", None, LocationLevel.COUNTRY, LocationConfidence.LOW),
    ("Deutschland", "DE", None, LocationLevel.COUNTRY, LocationConfidence.HIGH),
    ("United States of America", "US", None, LocationLevel.COUNTRY, LocationConfidence.HIGH),
    ("Berlin, Germany", "DE", "Berlin", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Toronto, Canada", "CA", "Toronto", LocationLevel.CITY, LocationConfidence.HIGH),
    ("São Paulo, Brazil", "BR", "São Paulo", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Kyiv, Ukraine", "UA", "Kyiv", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Shenzhen, China", "CN", "Shenzhen", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Munich, DE", "DE", "Munich", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Bangalore, IN", "IN", "Bengaluru", LocationLevel.CITY, LocationConfidence.HIGH),
    ("Tbilisi, Georgia", "GE", "Tbilisi", LocationLevel.CITY, LocationConfidence.HIGH),
    # State/region + city or country combinations are medium per spec 15.
    ("Austin, TX", "US", "Austin", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Cambridge, MA", "US", "Cambridge", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("San Francisco, CA", "US", "San Francisco", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Atlanta, Georgia", "US", "Atlanta", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Denver, CO", "US", "Denver", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Ontario, Canada", "CA", None, LocationLevel.REGION, LocationConfidence.MEDIUM),
    # Lone dominant cities are medium; ambiguous lone cities are low.
    ("Reykjavik", "IS", "Reykjavík", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Amsterdam", "NL", "Amsterdam", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("東京", "JP", "Tokyo", LocationLevel.CITY, LocationConfidence.MEDIUM),
    ("Springfield", "US", "Springfield", LocationLevel.CITY, LocationConfidence.LOW),
    # The Georgia trap: country name that is also a US state -> low.
    ("Georgia", "GE", None, LocationLevel.COUNTRY, LocationConfidence.LOW),
    # Broad regions alone are low.
    ("California", "US", None, LocationLevel.REGION, LocationConfidence.LOW),
    ("Scotland", "GB", None, LocationLevel.REGION, LocationConfidence.LOW),
]


@pytest.mark.parametrize(("raw", "country", "city", "level", "confidence"), GOLDEN)
def test_golden_table(
    config: AtlasConfig,
    gazetteer: Gazetteer,
    raw: str,
    country: str | None,
    city: str | None,
    level: LocationLevel,
    confidence: LocationConfidence,
) -> None:
    result = run(config, gazetteer, raw)
    assert result.normalized_country_code == country, result
    assert result.normalized_city == city, result
    assert result.location_level is level, result
    assert result.location_confidence is confidence, result


@pytest.mark.parametrize(
    "raw",
    ["", "  ", "Earth", "the internet", "Remote", "127.0.0.1", "🌍", "Milky Way", None],
)
def test_placeholders_and_empty_are_unusable(
    config: AtlasConfig, gazetteer: Gazetteer, raw: str | None
) -> None:
    result = run(config, gazetteer, raw)
    assert result.location_confidence is LocationConfidence.UNUSABLE
    assert result.normalization_method is NormalizationMethod.UNRESOLVED
    assert result.normalized_country_code is None


def test_conflicting_multi_locations_are_unusable(
    config: AtlasConfig, gazetteer: Gazetteer
) -> None:
    result = run(config, gazetteer, "London / Paris")
    assert result.location_confidence is LocationConfidence.UNUSABLE
    assert result.ambiguity_reason == "multiple conflicting locations"


def test_agreeing_multi_locations_resolve(config: AtlasConfig, gazetteer: Gazetteer) -> None:
    result = run(config, gazetteer, "Berlin / Munich")
    assert result.normalized_country_code == "DE"


def test_pipeline_order_override_beats_alias_beats_parsing(gazetteer: Gazetteer) -> None:
    aliases = [
        LocationAlias(
            alias="Atlantis",
            normalized_country_code="GR",
            normalized_city=None,
            location_level=LocationLevel.COUNTRY,
            notes="test",
        )
    ]
    overrides = [
        LocationOverride(
            raw_location="Atlantis",
            normalized_country_code="PT",
            normalized_city=None,
            location_level=LocationLevel.COUNTRY,
            evidence_note="test override evidence",
        )
    ]
    with_override = normalize_location(
        "u", "Atlantis", aliases=aliases, overrides=overrides, gazetteer=gazetteer
    )
    assert with_override.normalized_country_code == "PT"
    assert with_override.normalization_method is NormalizationMethod.MANUAL_OVERRIDE
    assert with_override.location_confidence is LocationConfidence.HIGH

    alias_only = normalize_location(
        "u", "Atlantis", aliases=aliases, overrides=[], gazetteer=gazetteer
    )
    assert alias_only.normalized_country_code == "GR"
    assert alias_only.normalization_method is NormalizationMethod.EXACT_ALIAS


def test_aggregation_eligibility_rules(config: AtlasConfig, gazetteer: Gazetteer) -> None:
    high_city = run(config, gazetteer, "Berlin, Germany")
    medium_city = run(config, gazetteer, "Austin, TX")
    low = run(config, gazetteer, "Springfield")
    unusable = run(config, gazetteer, "Earth")
    assert city_ranking_eligible(high_city)
    assert not city_ranking_eligible(medium_city)  # city rankings: high only
    assert country_ranking_eligible(medium_city)  # country rankings: high+medium
    assert not country_ranking_eligible(low)
    assert not country_ranking_eligible(unusable)


def test_runner_round_trip(config: AtlasConfig, gazetteer: Gazetteer, tmp_path: Path) -> None:
    profiles = pl.DataFrame(
        {
            "actor_login": ["a", "b", "c", "d", "e"],
            "fetch_status": ["success", "success", "success", "not_found", "success"],
            "public_location_raw": ["Berlin, Germany", "Earth", None, "Paris", "Austin, TX"],
        }
    )
    profiles_path = tmp_path / "profiles.parquet"
    profiles.write_parquet(profiles_path)
    output_path = tmp_path / "normalized.parquet"

    summary = normalize_profile_locations(config, profiles_path, output_path)
    assert summary.total == 5
    assert summary.located_country == 2  # Berlin + Austin
    assert summary.unusable == 3  # joke, null location, failed fetch
    assert 0.0 < summary.coverage_country_rate < 1.0

    written = pl.read_parquet(output_path)
    assert written.height == 5
    for row in written.iter_rows(named=True):
        NormalizedLocation.model_validate(row)  # schema-conformant, spec 9.6
    assert written["actor_login"].to_list() == sorted(written["actor_login"].to_list())
