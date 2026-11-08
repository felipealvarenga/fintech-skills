import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fx import convert_usd_to_jpy  # noqa: E402
from money import convert_minor, from_minor, to_minor  # noqa: E402


def test_usd_to_jpy_reference():
    assert convert_usd_to_jpy(1000) == 1505  # 10.00 USD -> 1505 JPY
    assert convert_usd_to_jpy(0) == 0
    assert convert_usd_to_jpy(-1000) == -1505


def test_usd_to_jpy_rounds_half_even_once():
    # 1 cent = 1.505 JPY -> 2 ; 3 cents = 4.515 -> 5 ; 50 cents = 75.25 -> 75
    assert convert_usd_to_jpy(1) == 2
    assert convert_usd_to_jpy(3) == 5
    assert convert_usd_to_jpy(50) == 75
    # exact half: 0.5 JPY -> 0 (even), 2.5 -> 2 under HALF_EVEN
    assert convert_minor(1, "USD", "JPY", Decimal("0.5")) == 0
    assert convert_minor(5, "USD", "JPY", Decimal("0.5")) == 2


def test_rejects_floats():
    with pytest.raises(TypeError):
        convert_usd_to_jpy(10.5)
    with pytest.raises(TypeError):
        convert_minor(1000, "USD", "JPY", 150.5)


def test_unknown_currency_refused():
    with pytest.raises(ValueError):
        convert_minor(100, "USD", "XXX", Decimal("1"))


def test_parse_too_many_decimals_refused():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")


@pytest.mark.parametrize("ccy,minor", [("JPY", 1505), ("USD", 1234), ("KWD", 12345)])
def test_round_trip(ccy, minor):
    assert to_minor(from_minor(minor, ccy), ccy) == minor
