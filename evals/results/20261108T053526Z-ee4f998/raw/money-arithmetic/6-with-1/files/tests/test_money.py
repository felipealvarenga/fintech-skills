import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from checkout_cents import to_cents, to_display  # noqa: E402
from money import from_minor, to_minor  # noqa: E402


@pytest.mark.parametrize("ccy", ["USD", "JPY", "KWD"])
@pytest.mark.parametrize("x", [0, 1, 5, 999, 123456, -1, -1234])
def test_round_trip(x, ccy):
    assert to_minor(from_minor(x, ccy), ccy) == x


def test_known_values():
    assert to_cents("12.34", "USD") == 1234
    assert to_cents("1234", "JPY") == 1234
    assert to_cents("1.234", "KWD") == 1234
    assert to_display(1234, "USD") == "12.34"
    assert to_display(1234, "JPY") == "1234"
    assert to_display(1234, "KWD") == "1.234"
    assert to_display(5, "KWD") == "0.005"
    assert to_display(-5, "USD") == "-0.05"


def test_too_many_decimals_refused():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")
    with pytest.raises(ValueError):
        to_minor("100.5", "JPY")
    with pytest.raises(ValueError):
        to_minor("1.2345", "KWD")


def test_unknown_currency_refused():
    with pytest.raises(ValueError):
        to_minor("1", "XXX")


def test_nan_and_garbage_refused():
    for bad in ["NaN", "Infinity", "abc"]:
        with pytest.raises(ValueError):
            to_minor(bad, "USD")
