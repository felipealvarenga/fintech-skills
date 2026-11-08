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
            ("100", "JPY", 100),
            ("1.5", "BHD", 1500),
            ("-12.34", "USD", -1234),
        ],
    )
    def test_exact_conversions(self, amount, currency, expected):
        assert to_minor(amount, currency) == expected

    def test_excess_precision_truncates_toward_zero(self):
        # Documents current behavior: extra digits are truncated, not rounded.
        # If rounding is intended, this is a bug in to_minor.
        assert to_minor("1.005", "USD") == 100
        assert to_minor("1.999", "USD") == 199
        assert to_minor("-1.999", "USD") == -199

    def test_unknown_currency_raises(self):
        with pytest.raises(KeyError):
            to_minor("1.00", "XXX")

    def test_invalid_amount_raises(self):
        with pytest.raises(Exception):
            to_minor("abc", "USD")


class TestAllocate:
    def test_even_split(self):
        assert allocate(100, [1, 1]) == [50, 50]

    def test_remainder_goes_to_first_on_ties(self):
        assert allocate(100, [1, 1, 1]) == [34, 33, 33]

    def test_proportional(self):
        assert allocate(100, [70, 30]) == [70, 30]

    def test_odd_amount(self):
        assert allocate(5, [1, 1]) == [3, 2]

    def test_remainder_goes_to_largest_fractional_part(self):
        # 10*[1,2]/3 -> 3.33, 6.67 ; the extra cent goes to the second share
        assert allocate(10, [1, 2]) == [3, 7]

    def test_zero_amount(self):
        assert allocate(0, [1, 2]) == [0, 0]

    def test_zero_ratio_gets_nothing(self):
        assert allocate(100, [0, 1]) == [0, 100]

    def test_single_ratio(self):
        assert allocate(123, [5]) == [123]

    def test_smaller_than_parties(self):
        assert allocate(1, [1, 1, 1]) == [1, 0, 0]

    def test_sum_is_always_preserved(self):
        for amount in range(-50, 200):
            for ratios in ([1, 1, 1], [1, 2, 3], [7, 3], [1, 0, 1], [13, 17, 19, 1]):
                result = allocate(amount, ratios)
                assert sum(result) == amount, (amount, ratios, result)
                assert len(result) == len(ratios)

    def test_non_negative_amount_gives_non_negative_shares(self):
        for amount in range(0, 100):
            assert all(s >= 0 for s in allocate(amount, [1, 2, 3]))

    def test_negative_amount_preserves_sum(self):
        assert sum(allocate(-100, [1, 1, 1])) == -100

    def test_empty_ratios_raises(self):
        with pytest.raises(ZeroDivisionError):
            allocate(100, [])

    def test_all_zero_ratios_raises(self):
        with pytest.raises(ZeroDivisionError):
            allocate(100, [0, 0])


class TestApplyRate:
    @pytest.mark.parametrize(
        "amount,rate,expected",
        [
            (100, "1.1", 110),
            (100, "1", 100),
            (100, "0", 0),
            (0, "5.25", 0),
            (105, "0.5", 52),   # 52.5 -> even
            (107, "0.5", 54),   # 53.5 -> even
            (-105, "0.5", -52),
            (-107, "0.5", -54),
            (3, "0.333", 1),    # 0.999 -> 1
            (10, "0.14", 1),    # 1.4 -> 1
            (10, "0.16", 2),    # 1.6 -> 2
        ],
    )
    def test_rounding_and_values(self, amount, rate, expected):
        assert apply_rate(amount, rate) == expected

    def test_returns_int(self):
        assert isinstance(apply_rate(100, "1.5"), int)

    def test_large_amount_is_exact(self):
        assert apply_rate(10**18, "1.5") == 15 * 10**17

    def test_invalid_rate_raises(self):
        with pytest.raises(Exception):
            apply_rate(100, "not-a-number")
