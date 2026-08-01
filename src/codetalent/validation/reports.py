"""Validation report generation (spec section 18 required outputs).

Produces ``reports/ranking_validation.md`` and the inputs for
``docs/bias_limitations.md`` and methodology coverage charts.
Target milestone: E.
"""

from __future__ import annotations

from pathlib import Path


def write_ranking_validation_report(processed_dir: Path, output_path: Path) -> Path:
    """Write the ranking validation report and return its path."""
    raise NotImplementedError("Milestone E implements validation reporting.")
