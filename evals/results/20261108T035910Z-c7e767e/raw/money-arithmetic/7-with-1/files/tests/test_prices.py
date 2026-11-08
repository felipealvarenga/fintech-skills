import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

import pytest
from prices import parse_price


@pytest.mark.parametrize("text,ccy,expected", [
    ("1.234,56", "BRL", 123456),
    ("1,234.56", "USD", 123456),
    ("1.234.567,89", "BRL", 123456789),
    ("1,234,567.89", "USD", 123456789),
    ("12,5", "BRL", 1250),
    ("12.5", "USD", 1250),
    ("1.234", "BRL", 123400),   # 3 digits after sep: grouping in a 2-decimal currency
    ("1,234", "USD", 123400),
    ("1234", "USD", 123400),
    ("0,99", "BRL", 99),
    ("-1.234,56", "BRL", -123456),
    ("1.234", "JPY", 1234),
    ("1.234,567", "KWD", 1234567),
])
def test_valid(text, ccy, expected):
    assert parse_price(text, ccy) == expected


@pytest.mark.parametrize("text,ccy", [
    ("12.345,678", "BRL"),   # too many decimals
    ("12,345", "KWD"),       # ambiguous in a 3-decimal currency
    ("1.23.4", "USD"),
    ("1,23,456.00", "USD"),  # bad grouping
    ("", "USD"), ("abc", "USD"), ("NaN", "USD"), ("1e5", "USD"), ("1,", "USD"),
    ("1.5", "JPY"),
    ("1", "XXX"),
])
def test_rejected(text, ccy):
    with pytest.raises(ValueError):
        parse_price(text, ccy)
