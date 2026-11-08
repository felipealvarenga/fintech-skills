import json
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from api_amount import serialize_payment  # noqa: E402
from money import from_minor, to_minor  # noqa: E402


def pay(amount, ccy="USD"):
    return SimpleNamespace(id="p1", amount=amount, currency=ccy)


def test_amount_is_string_not_number():
    assert json.loads(serialize_payment(pay(Decimal("12.34"))))["amount"] == "12.34"


def test_scales():
    assert json.loads(serialize_payment(pay(Decimal("5"), "USD")))["amount"] == "5.00"
    assert json.loads(serialize_payment(pay(Decimal("1234"), "JPY")))["amount"] == "1234"
    assert json.loads(serialize_payment(pay(Decimal("1.234"), "BHD")))["amount"] == "1.234"


@pytest.mark.parametrize("ccy,x", [("JPY", 0), ("JPY", 7), ("USD", 5), ("USD", -1234), ("BHD", 1234)])
def test_round_trip(ccy, x):
    assert to_minor(from_minor(x, ccy), ccy) == x


def test_refusals():
    with pytest.raises(ValueError):
        to_minor("12.345", "USD")
    with pytest.raises(ValueError):
        to_minor("1", "XXX")
    with pytest.raises(TypeError):
        serialize_payment(pay(12.34))
