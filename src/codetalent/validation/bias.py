"""Coverage-bias measurement and ranking sensitivity analysis (spec section 18).

Missing-location rates by activity decile, language, and organization size;
sensitivity runs removing top repositories/organizations and varying weights
by +/- 20%. Target milestone: E.
"""

from __future__ import annotations

from pathlib import Path


def measure_coverage_bias(processed_dir: Path) -> dict[str, float]:
    """Return coverage-bias metrics for the bias and limitations report."""
    raise NotImplementedError("Milestone E implements coverage-bias measurement.")


def run_sensitivity_analysis(processed_dir: Path, output_dir: Path) -> Path:
    """Write sensitivity CSVs and return the output directory."""
    raise NotImplementedError("Milestone E implements sensitivity analysis.")
