import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from money import from_minor, to_minor  # noqa: E402
from prices import parse_price  # noqa: E402


@pytest.mark.parametrize("text,expected", [
    ("1.234,56", 123456),
    ("1,234.56", 123456),
    ("1234,56", 123456),
    ("1234.56", 123456),
    ("0,5", 50),
    ("12", 1200),
    ("1.234.567,89", 123456789),
    ("1,234,567.89", 123456789),
    ("1.234", 123400),
    ("-1.234,56", -123456),
    (" 10,00 ", 1000),
])
def test_two_decimal(text, expected):
    assert parse_price(text, "USD") == expected
    assert parse_price(text, "BRL") == expected


@pytest.mark.parametrize("text", ["12,345", "1.2.3,4", "abc", "", "1,23,4", "1.234,5,6", ",", "12."])
def test_rejects(text):
    with pytest.raises(ValueError):
        parse_price(text, "USD")


def test_too_many_decimals_refused():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")
    with pytest.raises(ValueError):
        parse_price("12,345.6", "USD")


def test_unknown_currency():
    with pytest.raises(ValueError):
        parse_price("1,00", "XXX")


def test_zero_and_three_decimal_currencies():
    assert parse_price("1.234", "JPY") == 1234
    assert parse_price("1,234.567", "KWD") == 1234567
    with pytest.raises(ValueError):
        parse_price("1.234", "KWD")  # ambiguous


@pytest.mark.parametrize("ccy,x", [("USD", 123456), ("JPY", 987), ("KWD", -1234567), ("USD", 5)])
def test_round_trip(ccy, x):
    assert to_minor(from_minor(x, ccy), ccy) == x
