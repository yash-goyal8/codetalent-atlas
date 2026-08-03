"""Robust statistical scaling toolkit shared by all scoring engines (spec 16.1).

Spec 16.1 mandates robust scaling: percentile ranks, ``log1p``, winsorization
at the configured percentile, and bounded subscores so no single huge
repository (or contributor, or geography) sets the scale for everyone else.

Every function is a pure, deterministic transformation of a value sequence.
Degenerate inputs are handled explicitly:

- Empty input -> empty output (never an error).
- Single value or all-equal values -> **50.0** from :func:`minmax_to_100` and
  **0.5** from :func:`percentile_rank`. Rationale, documented per the build
  task: with no dispersion there is no evidence for "high" or "low", so every
  member sits at the neutral midpoint rather than an arbitrary extreme.

Percentiles use linear interpolation over the sorted values (the same scheme
as ``numpy``'s default), implemented locally so the toolkit stays dependency-
free and byte-deterministic.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

_WEIGHT_SUM_TOLERANCE = 1e-9
#: Slack for floating-point drift when asserting a subscore is within 0-100.
_BOUND_TOLERANCE = 1e-9


def percentile_value(values: Sequence[float], percentile: float) -> float:
    """Return the ``percentile`` (0-1) of ``values`` via linear interpolation.

    Deterministic; requires a non-empty input.
    """
    if not values:
        raise ValueError("percentile_value requires at least one value")
    if not 0.0 <= percentile <= 1.0:
        raise ValueError(f"percentile must be in [0, 1], got {percentile}")
    ordered = sorted(values)
    position = percentile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def winsorize(values: Sequence[float], upper_percentile: float) -> list[float]:
    """Clip values above the configured upper percentile (spec 16.1).

    Only the upper tail is clipped: the goal is to stop one mega repository
    from setting the scale, not to inflate small values.
    """
    if not values:
        return []
    ceiling = percentile_value(values, upper_percentile)
    return [min(value, ceiling) for value in values]


def percentile_rank(values: Sequence[float]) -> list[float]:
    """Return 0-1 percentile ranks preserving input order; ties share ranks.

    Each sorted position ``j`` (1-based) maps to ``(j - 0.5) / n``; tied values
    receive the average of their positions' ranks (deterministic average-rank
    tie handling). A single value ranks 0.5; all-equal inputs all rank 0.5.
    """
    n = len(values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: (values[i], i))
    ranks = [0.0] * n
    j = 0
    while j < n:
        k = j
        while k + 1 < n and values[order[k + 1]] == values[order[j]]:
            k += 1
        # Positions j..k (0-based) are tied; average their (pos + 0.5)/n ranks.
        average = (j + k + 1) / 2 / n
        for position in range(j, k + 1):
            ranks[order[position]] = average
        j = k + 1
    return ranks


def log1p_scale(values: Sequence[float]) -> list[float]:
    """Apply ``log1p`` elementwise; inputs must be non-negative."""
    for value in values:
        if value < 0:
            raise ValueError(f"log1p_scale requires non-negative values, got {value}")
    return [math.log1p(value) for value in values]


def minmax_to_100(values: Sequence[float]) -> list[float]:
    """Rescale into 0-100. Degenerate all-equal inputs map to 50.0 (documented)."""
    if not values:
        return []
    lower = min(values)
    upper = max(values)
    if upper == lower:
        return [50.0] * len(values)
    span = upper - lower
    return [(value - lower) / span * 100.0 for value in values]


def scale_count(values: Sequence[float], winsorization_percentile: float) -> list[float]:
    """Robust 0-100 magnitude scale for count-like signals (spec 16.1 recipe).

    winsorize at the configured percentile -> ``log1p`` -> min-max into 0-100.
    """
    return minmax_to_100(log1p_scale(winsorize(values, winsorization_percentile)))


def scale_rank(values: Sequence[float]) -> list[float]:
    """Pure-ordering 0-100 scale: percentile rank * 100 (average-rank ties)."""
    return [rank * 100.0 for rank in percentile_rank(values)]


def weighted_blend(
    subscores: Mapping[str, Sequence[float]], weights: Mapping[str, float]
) -> list[float]:
    """Blend bounded 0-100 subscores with weights that must sum to 1.0.

    Enforces the spec 28 quality gates at computation time: weights sum to 1.0
    within 1e-9, every subscore is within 0-100, and the output is the exact
    weighted sum (clamped only for floating-point dust at the boundaries).
    """
    if set(subscores) != set(weights):
        raise ValueError(
            f"subscore keys {sorted(subscores)} do not match weight keys {sorted(weights)}"
        )
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(f"blend weights must sum to 1.0, got {total_weight}")
    lengths = {len(series) for series in subscores.values()}
    if len(lengths) > 1:
        raise ValueError(f"subscore series lengths differ: {sorted(lengths)}")
    for name, series in subscores.items():
        for value in series:
            if not -_BOUND_TOLERANCE <= value <= 100.0 + _BOUND_TOLERANCE:
                raise ValueError(f"subscore {name!r} out of 0-100 bounds: {value}")
    length = lengths.pop() if lengths else 0
    blended: list[float] = []
    for index in range(length):
        value = sum(weights[name] * subscores[name][index] for name in weights)
        blended.append(min(max(value, 0.0), 100.0))
    return blended


def weighted_median(values: Sequence[float], weights: Sequence[float]) -> float:
    """Weighted median (spec 17 expert quality: never a simple mean).

    Sorts by value (stable) and returns the first value whose cumulative
    weight reaches half of the total weight. Deterministic for ties.
    """
    if not values:
        raise ValueError("weighted_median requires at least one value")
    if len(values) != len(weights):
        raise ValueError("values and weights must have equal length")
    for weight in weights:
        if weight < 0:
            raise ValueError(f"weights must be non-negative, got {weight}")
    total = sum(weights)
    if total <= 0:
        raise ValueError("weighted_median requires a positive total weight")
    pairs = sorted(zip(values, weights, strict=True), key=lambda pair: pair[0])
    half = total / 2.0
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= half:
            return value
    return pairs[-1][0]  # pragma: no cover - unreachable with positive total


def saturating_ratio(count: float, minimum: float, saturation_multiple: float) -> float:
    """Smooth 0-1 sample-adequacy ratio saturating at ``minimum * multiple``.

    ``count / (minimum * saturation_multiple)`` clipped to 1.0 — rises
    smoothly through the configured minimum instead of jumping at it
    (spec 17 sample-size adequacy).
    """
    if minimum <= 0:
        raise ValueError("minimum must be positive")
    if count < 0:
        raise ValueError("count must be non-negative")
    return min(count / (minimum * saturation_multiple), 1.0)
