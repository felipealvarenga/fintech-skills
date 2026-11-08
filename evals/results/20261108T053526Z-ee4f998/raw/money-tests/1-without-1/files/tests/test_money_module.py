import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from money_module import allocate, apply_rate, to_minor  # noqa: E402


class TestToMinor:
    @pytest.mark.parametrize(
        "amount,currency,expected",
        [
            ("10.00", "USD", 1000),
            ("10", "USD", 1000),
            ("0.01", "BRL", 1),
            ("0", "USD", 0),
            ("500", "JPY", 500),
            ("1.234", "BHD", 1234),
            ("-5.25", "USD", -525),
        ],
    )
    def test_exact_conversions(self, amount, currency, expected):
        assert to_minor(amount, currency) == expected

    def test_returns_int(self):
        assert isinstance(to_minor("1.00", "USD"), int)

    def test_unknown_currency_raises(self):
        with pytest.raises(KeyError):
            to_minor("1.00", "XXX")

    def test_invalid_amount_raises(self):
        with pytest.raises(Exception):
            to_minor("abc", "USD")

    def test_excess_precision_current_behavior_truncates(self):
        # Documents current behavior: extra precision is silently truncated
        # toward zero rather than rounded or rejected. This may be a bug for
        # money handling; revisit if the policy changes.
        assert to_minor("1.999", "USD") == 199
        assert to_minor("-1.999", "USD") == -199
        assert to_minor("1.5", "JPY") == 1


class TestAllocate:
    @pytest.mark.parametrize(
        "amount,ratios",
        [
            (100, [1, 1, 1]),
            (100, [1, 2, 3]),
            (1, [1, 1]),
            (0, [1, 2]),
            (1000, [70, 20, 10]),
            (7, [3, 3, 3, 3]),
            (5, [0, 1, 1]),
        ],
    )
    def test_sum_is_preserved(self, amount, ratios):
        assert sum(allocate(amount, ratios)) == amount

    def test_even_split_with_remainder(self):
        assert allocate(100, [1, 1, 1]) == [34, 33, 33]

    def test_proportional_exact(self):
        assert allocate(1000, [70, 20, 10]) == [700, 200, 100]

    def test_zero_ratio_gets_nothing(self):
        assert allocate(10, [0, 1]) == [0, 10]

    def test_single_ratio(self):
        assert allocate(123, [5]) == [123]

    def test_remainder_goes_to_largest_fraction(self):
        # 10 * [1,1,2] / 4 = [2.5, 2.5, 5]; remainder 0 -> exact floors 2,2,5 + 1 rem
        result = allocate(10, [1, 1, 2])
        assert sum(result) == 10
        assert result[2] == 5

    def test_negative_amount_preserves_sum(self):
        result = allocate(-100, [1, 1, 1])
        assert sum(result) == -100
        assert max(result) - min(result) <= 1

    def test_zero_total_ratio_raises(self):
        with pytest.raises(ZeroDivisionError):
            allocate(100, [0, 0])

    def test_empty_ratios_raises(self):
        with pytest.raises(ZeroDivisionError):
            allocate(100, [])

    def test_no_share_differs_from_ideal_by_more_than_one(self):
        amount, ratios = 101, [13, 29, 7, 51]
        total = sum(ratios)
        for share, r in zip(allocate(amount, ratios), ratios):
            assert abs(share - amount * r / total) < 1


class TestApplyRate:
    @pytest.mark.parametrize(
        "amount,rate,expected",
        [
            (100, "1", 100),
            (100, "0", 0),
            (100, "1.5", 150),
            (1000, "0.1", 100),
            (-100, "1.5", -150),
        ],
    )
    def test_exact(self, amount, rate, expected):
        assert apply_rate(amount, rate) == expected

    @pytest.mark.parametrize(
        "amount,rate,expected",
        [
            (1, "0.5", 0),    # 0.5 -> 0 (even)
            (3, "0.5", 2),    # 1.5 -> 2 (even)
            (5, "0.5", 2),    # 2.5 -> 2 (even)
            (7, "0.5", 4),    # 3.5 -> 4 (even)
            (-5, "0.5", -2),  # -2.5 -> -2 (even)
            (-3, "0.5", -2),  # -1.5 -> -2 (even)
        ],
    )
    def test_bankers_rounding(self, amount, rate, expected):
        assert apply_rate(amount, rate) == expected

    def test_non_tie_rounds_to_nearest(self):
        assert apply_rate(10, "0.26") == 3  # 2.6
        assert apply_rate(10, "0.24") == 2  # 2.4

    def test_returns_int(self):
        assert isinstance(apply_rate(10, "1.1"), int)

    def test_invalid_rate_raises(self):
        with pytest.raises(Exception):
            apply_rate(10, "abc")

    def test_high_precision_rate(self):
        assert apply_rate(1_000_000, "5.123456") == 5_123_456
