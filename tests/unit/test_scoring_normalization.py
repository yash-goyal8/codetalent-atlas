"""Exhaustive edge-case tests for the robust scaling toolkit (spec 16.1)."""

from __future__ import annotations

import pytest

from codetalent.scoring import normalization as norm


class TestPercentileValue:
    def test_linear_interpolation(self) -> None:
        assert norm.percentile_value([0.0, 10.0], 0.5) == pytest.approx(5.0)
        assert norm.percentile_value([1.0, 2.0, 3.0, 4.0], 0.25) == pytest.approx(1.75)

    def test_extremes(self) -> None:
        values = [5.0, 1.0, 3.0]
        assert norm.percentile_value(values, 0.0) == 1.0
        assert norm.percentile_value(values, 1.0) == 5.0

    def test_single_value(self) -> None:
        assert norm.percentile_value([7.0], 0.99) == 7.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one value"):
            norm.percentile_value([], 0.5)

    def test_out_of_range_percentile_raises(self) -> None:
        with pytest.raises(ValueError, match="percentile"):
            norm.percentile_value([1.0], 1.5)


class TestWinsorize:
    def test_clips_upper_tail_only(self) -> None:
        values = [float(v) for v in range(1, 101)] + [1_000_000.0]
        clipped = norm.winsorize(values, 0.99)
        assert max(clipped) < 1_000_000.0
        assert clipped[:99] == values[:99]  # lower values untouched

    def test_empty(self) -> None:
        assert norm.winsorize([], 0.99) == []

    def test_single(self) -> None:
        assert norm.winsorize([42.0], 0.99) == [42.0]

    def test_all_equal(self) -> None:
        assert norm.winsorize([3.0, 3.0, 3.0], 0.99) == [3.0, 3.0, 3.0]


class TestPercentileRank:
    def test_empty(self) -> None:
        assert norm.percentile_rank([]) == []

    def test_single_is_midpoint(self) -> None:
        assert norm.percentile_rank([9.0]) == [0.5]

    def test_all_equal_are_midpoint(self) -> None:
        assert norm.percentile_rank([2.0, 2.0, 2.0, 2.0]) == [0.5, 0.5, 0.5, 0.5]

    def test_ordering_preserved(self) -> None:
        ranks = norm.percentile_rank([30.0, 10.0, 20.0])
        assert ranks[1] < ranks[2] < ranks[0]

    def test_average_rank_ties(self) -> None:
        # values 1, 2, 2, 3 -> tied middle pair averages positions 2 and 3.
        ranks = norm.percentile_rank([1.0, 2.0, 2.0, 3.0])
        assert ranks[0] == pytest.approx(0.125)
        assert ranks[1] == ranks[2] == pytest.approx((0.375 + 0.625) / 2)
        assert ranks[3] == pytest.approx(0.875)

    def test_deterministic(self) -> None:
        values = [5.0, 1.0, 5.0, 3.0, 1.0]
        assert norm.percentile_rank(values) == norm.percentile_rank(values)


class TestLog1pScale:
    def test_zero_and_positive(self) -> None:
        scaled = norm.log1p_scale([0.0, 1.0])
        assert scaled[0] == 0.0
        assert scaled[1] > 0.0

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            norm.log1p_scale([-0.1])

    def test_empty(self) -> None:
        assert norm.log1p_scale([]) == []


class TestMinmaxTo100:
    def test_bounds(self) -> None:
        scaled = norm.minmax_to_100([1.0, 2.0, 3.0])
        assert scaled == [0.0, 50.0, 100.0]

    def test_all_equal_degenerate_is_50(self) -> None:
        assert norm.minmax_to_100([7.0, 7.0]) == [50.0, 50.0]

    def test_single_is_50(self) -> None:
        assert norm.minmax_to_100([123.0]) == [50.0]

    def test_empty(self) -> None:
        assert norm.minmax_to_100([]) == []


class TestScaleCount:
    def test_bounded_and_monotone(self) -> None:
        scaled = norm.scale_count([0.0, 10.0, 100.0, 1000.0], 0.99)
        assert scaled[0] == 0.0
        assert scaled == sorted(scaled)
        assert all(0.0 <= value <= 100.0 for value in scaled)

    def test_mega_value_does_not_crush_others(self) -> None:
        # 100 ordinary values and one mega value: winsorization at p99 plus
        # log1p keeps the ordinary values spread over the scale instead of
        # collapsing them to ~0.
        values = [float(v) for v in range(1, 101)] + [10_000_000.0]
        scaled = norm.scale_count(values, 0.99)
        ordinary = scaled[:100]
        assert max(ordinary) - min(ordinary) > 50.0

    def test_empty(self) -> None:
        assert norm.scale_count([], 0.99) == []


class TestScaleRank:
    def test_range(self) -> None:
        scaled = norm.scale_rank([1.0, 2.0, 3.0, 4.0])
        assert scaled == [12.5, 37.5, 62.5, 87.5]


class TestWeightedBlend:
    def test_exact_weighted_sum(self) -> None:
        blended = norm.weighted_blend({"a": [100.0, 0.0], "b": [0.0, 100.0]}, {"a": 0.7, "b": 0.3})
        assert blended == [70.0, 30.0]

    def test_weights_must_sum_to_one_within_tolerance(self) -> None:
        with pytest.raises(ValueError, match=r"sum to 1\.0"):
            norm.weighted_blend({"a": [1.0]}, {"a": 0.9})
        # Well inside 1e-9 tolerance is accepted.
        result = norm.weighted_blend({"a": [10.0]}, {"a": 1.0 + 1e-12})
        assert result == pytest.approx([10.0])

    def test_key_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="do not match"):
            norm.weighted_blend({"a": [1.0]}, {"b": 1.0})

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="lengths differ"):
            norm.weighted_blend({"a": [1.0], "b": [1.0, 2.0]}, {"a": 0.5, "b": 0.5})

    def test_out_of_bounds_subscore_raises(self) -> None:
        with pytest.raises(ValueError, match="out of 0-100 bounds"):
            norm.weighted_blend({"a": [101.0]}, {"a": 1.0})
        with pytest.raises(ValueError, match="out of 0-100 bounds"):
            norm.weighted_blend({"a": [-1.0]}, {"a": 1.0})

    def test_empty_series(self) -> None:
        assert norm.weighted_blend({"a": [], "b": []}, {"a": 0.5, "b": 0.5}) == []


class TestWeightedMedian:
    def test_resists_outliers(self) -> None:
        # A simple mean would be dragged to 61.25 by the outlier.
        assert norm.weighted_median([50.0, 50.0, 50.0, 95.0], [1.0, 1.0, 1.0, 1.0]) == 50.0

    def test_weights_shift_the_median(self) -> None:
        assert norm.weighted_median([10.0, 90.0], [10.0, 1.0]) == 10.0
        assert norm.weighted_median([10.0, 90.0], [1.0, 10.0]) == 90.0

    def test_single_value(self) -> None:
        assert norm.weighted_median([42.0], [0.5]) == 42.0

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one value"):
            norm.weighted_median([], [])

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal length"):
            norm.weighted_median([1.0], [1.0, 2.0])

    def test_negative_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            norm.weighted_median([1.0], [-1.0])

    def test_zero_total_weight_raises(self) -> None:
        with pytest.raises(ValueError, match="positive total weight"):
            norm.weighted_median([1.0], [0.0])


class TestSaturatingRatio:
    def test_smooth_through_minimum(self) -> None:
        # Saturation multiple 2: half marks exactly at the minimum.
        assert norm.saturating_ratio(0, 10, 2.0) == 0.0
        assert norm.saturating_ratio(10, 10, 2.0) == pytest.approx(0.5)
        assert norm.saturating_ratio(20, 10, 2.0) == 1.0
        assert norm.saturating_ratio(1000, 10, 2.0) == 1.0

    def test_invalid_inputs_raise(self) -> None:
        with pytest.raises(ValueError, match="minimum"):
            norm.saturating_ratio(1, 0, 2.0)
        with pytest.raises(ValueError, match="count"):
            norm.saturating_ratio(-1, 10, 2.0)
