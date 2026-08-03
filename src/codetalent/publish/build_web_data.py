"""Static web dataset builder (spec sections 19-20, 27).

Emits exactly the section-20 JSON contract consumed by the dashboard, from the
local scored parquets, into BOTH ``web/public/data/`` and ``data/public/``.
Aggregates only: no usernames, no raw locations, no user-level rows. The
public-data privacy scanner runs over the output as the final step and any
violation aborts the publish and removes the output (spec 26/27).

Every number is computed from the pipeline parquets; the only free text is
template-assembled from those numbers (spec 19.5/19.7: templates, no model).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from codetalent.config import AtlasConfig
from codetalent.locations.gazetteer import shared_gazetteer
from codetalent.schemas import LocationConfidence
from codetalent.validation.privacy import scan_public_data

INTERIM = Path("data/interim")
WEB_DATA_DIR = Path("web/public/data")
PUBLIC_DATA_DIR = Path("data/public")

METHODOLOGY_VERSION = "1.0.0"

_CAMEL_OVERRIDES = {"geo_id": "geoId"}


def _camel(name: str) -> str:
    if name in _CAMEL_OVERRIDES:
        return _CAMEL_OVERRIDES[name]
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _round(value: Any, digits: int = 4) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    return value


def ranking_row_to_json(row: dict[str, Any], display_name: str) -> dict[str, Any]:
    """One spec 9.8 parquet row -> the camelCase contract row."""
    payload = {
        _camel(key): _round(value)
        for key, value in row.items()
        if key not in ("org_concentration_share", "org_concentration_flag")
    }
    payload["name"] = display_name
    payload["momentumProvisional"] = True  # three-month pilot (spec 17)
    return payload


def city_slug(geo_id: str) -> str:
    return geo_id.lower().replace("/", "-").replace(" ", "-")


@dataclass
class PublishInputs:
    """Everything the builder reads, loaded once."""

    rankings: pl.DataFrame
    contributor_scores: pl.DataFrame
    contributor_activity: pl.DataFrame
    classification: pl.DataFrame
    normalized_locations: pl.DataFrame
    monthly_trend: pl.DataFrame | None
    validation_numbers: dict[str, Any]


def load_inputs(interim: Path = INTERIM) -> PublishInputs:
    trend_path = interim / "geo_monthly_trend.parquet"
    validation_path = Path("reports/validation_summary.json")
    validation_numbers: dict[str, Any] = {}
    if validation_path.is_file():
        validation_numbers = json.loads(validation_path.read_text(encoding="utf-8"))
    return PublishInputs(
        rankings=pl.read_parquet(interim / "geographic_rankings.parquet"),
        contributor_scores=pl.read_parquet(interim / "contributor_scores.parquet"),
        contributor_activity=pl.read_parquet(interim / "contributor_activity.parquet"),
        classification=pl.read_parquet(interim / "repository_classification.parquet"),
        normalized_locations=pl.read_parquet(interim / "normalized_locations.parquet"),
        monthly_trend=pl.read_parquet(trend_path) if trend_path.is_file() else None,
        validation_numbers=validation_numbers,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _clear_dir(directory: Path, keep: tuple[str, ...] = (".gitkeep", "README.md")) -> None:
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return
    for child in directory.iterdir():
        if child.name in keep:
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def build_web_data(
    config: AtlasConfig,
    *,
    domain_id: str = "cloud_devops",
    window_start: str = "2026-05-01",
    window_end: str = "2026-07-31",
    dataset_version: str | None = None,
    out_dirs: tuple[Path, ...] = (WEB_DATA_DIR, PUBLIC_DATA_DIR),
    interim: Path = INTERIM,
) -> dict[str, Any]:
    """Build every contract file; returns the manifest. Deterministic given inputs."""
    inputs = load_inputs(interim)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    version = dataset_version or f"{generated_at[:10].replace('-', '.')}-pilot.1"
    gaz = shared_gazetteer()

    def display_name(country_code: str | None, city: str | None) -> str:
        if city:
            return city
        if country_code:
            return gaz.country_name_for(country_code) or country_code
        return "Unknown"

    def subdomain_display(subdomain_id: str) -> str:
        taxonomy = config.taxonomies.get(domain_id)
        sub = taxonomy.subdomains.get(subdomain_id) if taxonomy is not None else None
        return sub.display_name if sub is not None else subdomain_id

    primary = out_dirs[0]
    _clear_dir(primary)

    rankings = inputs.rankings.filter(pl.col("domain_id") == domain_id)
    countries = rankings.filter(pl.col("geo_level") == "country").sort("rank")
    cities = rankings.filter(pl.col("geo_level") == "city").sort("rank")

    def rows_json(frame: pl.DataFrame) -> list[dict[str, Any]]:
        return [
            ranking_row_to_json(row, display_name(row["country_code"], row["city"]))
            for row in frame.iter_rows(named=True)
        ]

    country_rows = rows_json(countries)
    city_rows = rows_json(cities)

    _write_json(
        primary / f"rankings/{domain_id}/countries.json",
        {
            "domainId": domain_id,
            "geoLevel": "country",
            "generatedAt": generated_at,
            "rows": country_rows,
        },
    )
    _write_json(
        primary / f"rankings/{domain_id}/cities.json",
        {"domainId": domain_id, "geoLevel": "city", "generatedAt": generated_at, "rows": city_rows},
    )

    located = inputs.normalized_locations
    country_eligible = located.filter(
        pl.col("normalized_country_code").is_not_null()
        & pl.col("location_confidence").is_in(
            [LocationConfidence.HIGH.value, LocationConfidence.MEDIUM.value]
        )
    )
    profiles_total = located.height
    sufficient = countries.filter(pl.col("recommendation_tier") != "insufficient_data")
    top_priority = [
        {
            "geoId": r["geoId"],
            "countryCode": r["countryCode"],
            "name": r["name"],
            "opportunityScore": r["opportunityScore"],
            "confidenceScore": r["confidenceScore"],
            "tier": r["recommendationTier"],
        }
        for r in country_rows
        if r["recommendationTier"] != "insufficient_data"
    ][:5]

    qualified = inputs.classification.filter(pl.col("classification_status") == "accepted")
    sub_exploded = qualified.select("repo_name", "subdomains").explode("subdomains").drop_nulls()
    actor_geo = inputs.contributor_scores.select("actor_login", "country_code").drop_nulls()
    activity_repo_actor = inputs.contributor_activity.select("actor_login", "repo_name").unique()
    sub_by_country = (
        sub_exploded.join(activity_repo_actor, on="repo_name")
        .join(actor_geo, on="actor_login")
        .group_by("subdomains", "country_code")
        .agg(pl.col("actor_login").n_unique().alias("experts"))
        .sort(["subdomains", "experts", "country_code"], descending=[False, True, False])
    )
    sub_hubs = []
    for sub_id in sorted(sub_exploded["subdomains"].unique().to_list()):
        rows = sub_by_country.filter(pl.col("subdomains") == sub_id)
        if rows.height == 0:
            continue
        top = rows.row(0, named=True)
        sub_hubs.append(
            {
                "subdomainId": sub_id,
                "displayName": subdomain_display(sub_id),
                "topCountry": gaz.country_name_for(top["country_code"]) or top["country_code"],
                "expertCount": int(top["experts"]),
            }
        )

    _write_json(
        primary / "summary.json",
        {
            "domainId": domain_id,
            "window": {"start": window_start, "end": window_end},
            "kpis": {
                "qualifiedRepositories": int(qualified.height),
                "observableExperts": int(inputs.contributor_scores.height),
                "locatedProfileCoverage": _round(
                    country_eligible.height / profiles_total if profiles_total else 0.0
                ),
                "countriesWithSufficientData": int(sufficient.height),
            },
            "topPriorityLocations": top_priority,
            "subdomainHubs": sub_hubs,
        },
    )

    trend = inputs.monthly_trend
    for row in country_rows:
        code = row["countryCode"]
        source = countries.filter(pl.col("country_code") == code).row(0, named=True)
        caveats: list[str] = []
        if row["locatedProfileCoverage"] < 0.4:
            caveats.append(
                f"Only {row['locatedProfileCoverage']:.0%} of observable contributors have a "
                "usable public location; treat rankings directionally."
            )
        if source["org_concentration_flag"]:
            caveats.append(
                f"A single organization accounts for {source['org_concentration_share']:.0%} "
                "of weighted activity (concentration risk)."
            )
        caveats.append("Momentum is provisional: three-month pilot window only.")
        activity_trend: list[dict[str, Any]] = []
        if trend is not None:
            activity_trend = [
                {
                    "month": str(t["month"]),
                    "events": int(t["events"]),
                    "activeContributors": int(t["active_contributors"]),
                }
                for t in trend.filter(pl.col("country_code") == code)
                .sort("month")
                .iter_rows(named=True)
            ]
        sub_mix_rows = (
            sub_exploded.join(activity_repo_actor, on="repo_name")
            .join(actor_geo.filter(pl.col("country_code") == code), on="actor_login")
            .group_by("subdomains")
            .agg(pl.col("actor_login").n_unique().alias("experts"))
            .sort(["experts", "subdomains"], descending=[True, False])
        )
        total_sub = max(int(sub_mix_rows["experts"].sum() or 0), 1)
        _write_json(
            primary / f"locations/countries/{code}.json",
            {
                "ranking": row,
                "components": {
                    "expertSupplyScore": row["expertSupplyScore"],
                    "expertQualityScore": row["expertQualityScore"],
                    "collaborationDepthScore": row["collaborationDepthScore"],
                    "momentumScore": row["momentumScore"],
                    "ecosystemBreadthScore": row["ecosystemBreadthScore"],
                },
                "subdomainMix": [
                    {
                        "subdomainId": s["subdomains"],
                        "displayName": subdomain_display(s["subdomains"]),
                        "expertCount": int(s["experts"]),
                        "share": _round(int(s["experts"]) / total_sub),
                    }
                    for s in sub_mix_rows.iter_rows(named=True)
                ],
                "activityTrend": activity_trend,
                "concentration": {
                    "topOrgShare": _round(float(source["org_concentration_share"])),
                    "singleRepoShare": None,
                    "flagged": bool(source["org_concentration_flag"]),
                },
                "coverage": {
                    "locatedProfileCoverage": row["locatedProfileCoverage"],
                    "highConfidenceLocationShare": row["highConfidenceLocationShare"],
                    "observableExpertCount": row["observableExpertCount"],
                },
                "caveats": caveats,
            },
        )
    for row in city_rows:
        _write_json(
            primary / f"locations/cities/{city_slug(row['geoId'])}.json",
            {
                "ranking": row,
                "components": {
                    "expertSupplyScore": row["expertSupplyScore"],
                    "expertQualityScore": row["expertQualityScore"],
                    "collaborationDepthScore": row["collaborationDepthScore"],
                    "momentumScore": row["momentumScore"],
                    "ecosystemBreadthScore": row["ecosystemBreadthScore"],
                },
                "subdomainMix": [],
                "activityTrend": [],
                "concentration": {"topOrgShare": None, "singleRepoShare": None, "flagged": False},
                "coverage": {
                    "locatedProfileCoverage": row["locatedProfileCoverage"],
                    "highConfidenceLocationShare": row["highConfidenceLocationShare"],
                    "observableExpertCount": row["observableExpertCount"],
                },
                "caveats": ["City rankings use high-confidence city locations only."],
            },
        )

    _write_json(primary / f"compare/{domain_id}.json", {"rows": country_rows + city_rows})

    validation = inputs.validation_numbers
    _write_json(
        primary / "methodology/validation.json",
        {
            "classificationPrecision": validation.get("classificationPrecision"),
            "locationCountryPrecision": validation.get("locationCountryPrecision"),
            "locationCityPrecision": validation.get("locationCityPrecision"),
            "qualityChecks": validation.get("qualityChecks") or [],
            "funnel": validation.get("funnel") or [],
            "budget": validation.get("budget"),
        },
    )
    coverage_by_country = (
        country_eligible.group_by("normalized_country_code")
        .agg(pl.len().alias("located"))
        .sort(["located", "normalized_country_code"], descending=[True, False])
        .head(40)
    )
    confidence_dist = (
        located.group_by("location_confidence").agg(pl.len().alias("count")).sort("count")
    )
    _write_json(
        primary / "methodology/coverage.json",
        {
            "locatedShareByCountry": [
                {
                    "countryCode": r["normalized_country_code"],
                    "name": gaz.country_name_for(r["normalized_country_code"])
                    or r["normalized_country_code"],
                    "share": _round(r["located"] / max(country_eligible.height, 1)),
                    "expertCount": int(r["located"]),
                }
                for r in coverage_by_country.iter_rows(named=True)
            ],
            "confidenceDistribution": [
                {"level": r["location_confidence"], "count": int(r["count"])}
                for r in confidence_dist.iter_rows(named=True)
            ],
        },
    )

    rec_items = []
    for row in [r for r in country_rows if r["recommendationTier"] != "insufficient_data"][:3]:
        components = {
            "expert supply": row["expertSupplyScore"],
            "expert quality": row["expertQualityScore"],
            "collaboration depth": row["collaborationDepthScore"],
            "ecosystem breadth": row["ecosystemBreadthScore"],
        }
        strongest = max(components, key=lambda k: components[k])
        weakest = min(components, key=lambda k: components[k])
        sub_names = [subdomain_display(s) for s in row["topSubdomains"][:2]]
        rec_items.append(
            {
                "rank": row["rank"],
                "geoId": row["geoId"],
                "name": row["name"],
                "subdomains": sub_names,
                "opportunityScore": row["opportunityScore"],
                "confidenceScore": row["confidenceScore"],
                "observablePool": row["observableExpertCount"],
                "whyNow": (
                    f"{row['name']} ranks #{row['rank']} with opportunity "
                    f"{row['opportunityScore']:.1f} and confidence {row['confidenceScore']:.1f}; "
                    f"strongest component: {strongest} ({components[strongest]:.1f}). "
                    f"{row['observableExpertCount']} observable experts across "
                    f"{row['qualifiedRepoCount']} qualified repositories and "
                    f"{row['organizationCount']} organizations."
                ),
                "risk": (
                    f"Weakest component: {weakest} ({components[weakest]:.1f}); located-profile "
                    f"coverage {row['locatedProfileCoverage']:.0%}. Momentum provisional "
                    "(three-month pilot)."
                ),
                "suggestedPilot": (
                    "Run a small sourcing pilot targeting "
                    f"{' and '.join(sub_names) or 'the top subdomains'} contributors; validate "
                    "response and qualification rates before scaling."
                ),
            }
        )
    _write_json(
        primary / f"recommendations/{domain_id}.json",
        {"generatedAt": generated_at, "items": rec_items},
    )

    manifest = {
        "datasetVersion": version,
        "generatedAt": generated_at,
        "window": {"start": window_start, "end": window_end},
        "domains": [domain_id],
        "files": {
            "summary": "summary.json",
            "countryRankings": f"rankings/{domain_id}/countries.json",
            "cityRankings": f"rankings/{domain_id}/cities.json",
            "compare": f"compare/{domain_id}.json",
            "validation": "methodology/validation.json",
            "coverage": "methodology/coverage.json",
            "recommendations": f"recommendations/{domain_id}.json",
        },
        "methodologyVersion": METHODOLOGY_VERSION,
    }
    _write_json(primary / "manifest.json", manifest)

    for mirror in out_dirs[1:]:
        _clear_dir(mirror)
        shutil.copytree(primary, mirror, dirs_exist_ok=True)

    violations = scan_public_data(tuple(out_dirs))
    if violations:
        for directory in out_dirs:
            _clear_dir(directory)
        details = "; ".join(f"{v.file}: {v.pattern}" for v in violations[:5])
        raise RuntimeError(
            f"privacy scan found {len(violations)} violation(s) — publish aborted and "
            f"output removed: {details}"
        )
    return manifest
