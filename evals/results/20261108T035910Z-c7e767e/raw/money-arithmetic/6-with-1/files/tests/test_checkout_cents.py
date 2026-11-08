import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from checkout_cents import to_cents, to_display  # noqa: E402


@pytest.mark.parametrize("amount,ccy,minor", [
    ("12.34", "USD", 1234),
    ("1500", "JPY", 1500),
    ("1.234", "KWD", 1234),
    ("0.005", "KWD", 5),
    ("-1.500", "KWD", -1500),
])
def test_round_trip(amount, ccy, minor):
    assert to_cents(amount, ccy) == minor
    assert to_cents(to_display(minor, ccy), ccy) == minor


def test_display():
    assert to_display(1234, "KWD") == "1.234"
    assert to_display(1500, "JPY") == "1500"
    assert to_display(5, "USD") == "0.05"
    assert to_display(-5, "KWD") == "-0.005"


@pytest.mark.parametrize("amount,ccy", [
    ("12.345", "USD"), ("1.5", "JPY"), ("1.2345", "KWD"), ("NaN", "USD"),
])
def test_too_many_decimals_or_invalid(amount, ccy):
    with pytest.raises(ValueError):
        to_cents(amount, ccy)


def test_unknown_currency():
    with pytest.raises(ValueError):
        to_cents("1", "XXX")
    with pytest.raises(ValueError):
        to_display(1, "XXX")
