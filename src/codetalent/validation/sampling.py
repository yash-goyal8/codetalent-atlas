"""Stratified manual-validation sampling (spec sections 12, 15).

Builds the 150-repository classification sample (50 accepted / 50 rejected /
50 borderline) and the 500-location stratified review sample.
Target milestones: C (repositories), D (locations).
"""

from __future__ import annotations

from pathlib import Path


def build_classification_sample(classified_path: Path, output_path: Path, *, seed: int) -> Path:
    """Write the stratified 150-repository manual review sample."""
    raise NotImplementedError("Milestone C implements classification sampling.")


def build_location_sample(locations_path: Path, output_path: Path, *, seed: int) -> Path:
    """Write the stratified 500-location manual review sample."""
    raise NotImplementedError("Milestone D implements location sampling.")
