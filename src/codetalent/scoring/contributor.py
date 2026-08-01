"""Contributor expert score (spec 16.2): 0-100 domain-specific evidence score.

35% domain activity + 25% contribution quality + 20% repository quality
exposure + 10% continuity + 10% collaboration, with the bias safeguards
(no followers, 40% single-repository cap, push-volume cap, two meaningful
active days minimum) from ``config/scoring.yaml``. Target milestone: E.
"""

from __future__ import annotations

from codetalent.config import ScoringConfig
from codetalent.schemas import ContributorActivity, ContributorScore


def score_contributor(
    activity: list[ContributorActivity],
    repository_quality: dict[str, float],
    config: ScoringConfig,
) -> ContributorScore:
    """Return one contributor's spec 9.7 score record for a domain."""
    raise NotImplementedError("Milestone E implements contributor expert scoring.")
