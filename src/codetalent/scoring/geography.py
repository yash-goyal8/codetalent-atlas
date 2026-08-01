"""Country/city opportunity, confidence, and tier assignment (spec section 17).

Opportunity and confidence are computed and published separately; minimum
sample rules and tier thresholds come from ``config/scoring.yaml``.
Target milestone: E.
"""

from __future__ import annotations

from codetalent.config import ScoringConfig
from codetalent.schemas import ContributorScore, GeographicRanking, GeoLevel


def rank_geographies(
    contributor_scores: list[ContributorScore],
    config: ScoringConfig,
    *,
    geo_level: GeoLevel,
    domain_id: str,
) -> list[GeographicRanking]:
    """Return spec 9.8 ranking records with opportunity, confidence, and tiers."""
    raise NotImplementedError("Milestone E implements geographic ranking.")
