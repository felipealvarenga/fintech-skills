import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from dataclasses import fields

from customer_model import PaymentMethod

FORBIDDEN = {"pan", "card_number", "cvv", "cvc", "security_code"}


def make():
    return PaymentMethod("c1", "visa", "4242", "tok_abc", 12, 2030)


def test_schema_has_no_forbidden_fields():
    assert not FORBIDDEN & {f.name for f in fields(PaymentMethod)}


def test_public_dict_excludes_token_and_forbidden():
    d = make().to_public_dict()
    assert "token" not in d
    assert not FORBIDDEN & set(d)
    assert d["last4"] == "4242"


def test_rejects_full_pan_as_last4():
    with pytest.raises(ValueError):
        PaymentMethod("c1", "visa", "4242424242424242", "tok", 12, 2030)


def test_repr_does_not_matter_for_pan():
    assert "4242424242424242" not in repr(make())
