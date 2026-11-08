import dataclasses
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from customer_model import Customer, PaymentMethod  # noqa: E402

FORBIDDEN = re.compile(r"(^pan$|card_?number|cvv|cvc|security_code)", re.I)


def test_no_forbidden_card_fields():
    for cls in (Customer, PaymentMethod):
        for f in dataclasses.fields(cls):
            assert not FORBIDDEN.search(f.name), f"{cls.__name__}.{f.name}"


def test_last4_validation():
    import pytest
    with pytest.raises(ValueError):
        PaymentMethod("c1", "visa", "4242424242424242", "tok_1", "stripe")
