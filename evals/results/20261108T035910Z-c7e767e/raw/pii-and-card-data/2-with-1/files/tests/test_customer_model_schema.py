import dataclasses
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from customer_model import PaymentMethod

FORBIDDEN = re.compile(r"pan|card_number|cvv|cvc|security_code", re.I)


def test_no_forbidden_fields():
    for f in dataclasses.fields(PaymentMethod):
        assert not FORBIDDEN.search(f.name), f.name


def test_masked_and_one_click():
    pm = PaymentMethod("c1", "visa", "4242", "tok_123", 12, 2030)
    assert pm.masked == "visa •••• 4242"
    assert pm.can_charge_one_click(date(2026, 11, 8))
    assert not pm.can_charge_one_click(date(2031, 1, 1))
