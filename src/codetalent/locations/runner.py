"""Batch location normalization over enriched user profiles (Milestone D).

Reads the local (gitignored) user-profile parquet, normalizes every profile's
public location through the spec-15 pipeline, and writes the spec 9.6
NormalizedLocation parquet. Local-only: actor_login -> location mappings are
never committed or published (spec 15 privacy).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl

from codetalent.config import AtlasConfig
from codetalent.locations.gazetteer import shared_gazetteer
from codetalent.locations.normalize import normalize_location
from codetalent.runlog import RunLogger
from codetalent.schemas import LocationConfidence, NormalizedLocation


@dataclass(frozen=True)
class NormalizationRunSummary:
    """Counts for CLI display and the feasibility/coverage reports."""

    total: int
    located_country: int
    located_city: int
    unusable: int
    coverage_country_rate: float
    output_path: Path


def normalize_profile_locations(
    config: AtlasConfig,
    profiles_path: Path,
    output_path: Path,
) -> NormalizationRunSummary:
    """Normalize every successfully fetched profile's location. Deterministic."""
    log = RunLogger("locations-normalize")
    profiles = pl.read_parquet(profiles_path).sort("actor_login")
    gazetteer = shared_gazetteer()

    rows: list[NormalizedLocation] = []
    for login, status, raw in profiles.select(
        "actor_login", "fetch_status", "public_location_raw"
    ).iter_rows():
        if status != "success" or raw is None or not str(raw).strip():
            rows.append(
                normalize_location(
                    login,
                    None,
                    aliases=config.location_aliases,
                    overrides=config.location_overrides,
                    gazetteer=gazetteer,
                )
            )
            continue
        rows.append(
            normalize_location(
                login,
                str(raw),
                aliases=config.location_aliases,
                overrides=config.location_overrides,
                gazetteer=gazetteer,
            )
        )

    frame = pl.DataFrame(
        [row.model_dump(mode="json") for row in rows],
        schema={
            "actor_login": pl.Utf8,
            "raw_location": pl.Utf8,
            "normalized_country_code": pl.Utf8,
            "normalized_country_name": pl.Utf8,
            "normalized_city": pl.Utf8,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "location_level": pl.Utf8,
            "location_confidence": pl.Utf8,
            "normalization_method": pl.Utf8,
            "ambiguity_reason": pl.Utf8,
        },
    ).sort("actor_login")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_name(output_path.name + ".tmp")
    frame.write_parquet(tmp)
    tmp.replace(output_path)

    located_country = sum(1 for r in rows if r.normalized_country_code is not None)
    located_city = sum(1 for r in rows if r.normalized_city is not None)
    unusable = sum(1 for r in rows if r.location_confidence is LocationConfidence.UNUSABLE)
    total = len(rows)
    summary = NormalizationRunSummary(
        total=total,
        located_country=located_country,
        located_city=located_city,
        unusable=unusable,
        coverage_country_rate=located_country / total if total else 0.0,
        output_path=output_path,
    )
    log.step(
        "normalize",
        "completed",
        records_in=total,
        records_out=located_country,
    )
    return summary
