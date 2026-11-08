import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from api_amount import serialize_payment  # noqa: E402
from money import from_minor, to_minor  # noqa: E402


@pytest.mark.parametrize("ccy,x", [("JPY", 1234), ("USD", 1234), ("USD", -5), ("BHD", 1234), ("BHD", 7)])
def test_round_trip(ccy, x):
    assert to_minor(from_minor(x, ccy), ccy) == x


def test_too_many_decimals_refused():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")


def test_unknown_currency_refused():
    with pytest.raises(ValueError):
        to_minor("1", "XXX")


def test_float_refused():
    with pytest.raises(TypeError):
        to_minor(12.34, "USD")


@pytest.mark.parametrize("amount,ccy,expected", [
    (Decimal("12.34"), "USD", "12.34"),
    (Decimal("12.3"), "USD", "12.30"),
    (Decimal("1234"), "JPY", "1234"),
    (Decimal("1.234"), "BHD", "1.234"),
])
def test_wire_amount_is_string(amount, ccy, expected):
    out = json.loads(serialize_payment(SimpleNamespace(id=1, amount=amount, currency=ccy)))
    assert out["amount"] == expected
