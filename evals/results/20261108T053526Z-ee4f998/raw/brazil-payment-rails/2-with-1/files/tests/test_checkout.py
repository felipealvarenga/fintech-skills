import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from checkout import Order, can_download, confirm_boleto_payment, generate_boleto  # noqa: E402


class FakePSP:
    def __init__(self, nosso="000123"):
        self.nosso = nosso

    def create_boleto(self, order):
        return {"linha_digitavel": "1" * 47, "nosso_numero": self.nosso, "vencimento": "2026-12-01"}


def test_issuance_does_not_fulfil():
    o = Order("o1")
    generate_boleto(o, FakePSP())
    assert o.status == "pending"
    assert not can_download(o)


def test_return_marks_paid_and_releases_download():
    o = Order("o1")
    generate_boleto(o, FakePSP())
    assert confirm_boleto_payment(o, "000123") is True
    assert o.status == "paid" and can_download(o)


def test_nosso_numero_leading_zeros_preserved():
    o = Order("o1")
    generate_boleto(o, FakePSP("000123"))
    with pytest.raises(ValueError):
        confirm_boleto_payment(o, "123")
    assert o.status == "pending"


def test_confirmation_is_idempotent():
    o = Order("o1")
    generate_boleto(o, FakePSP())
    assert confirm_boleto_payment(o, "000123") is True
    assert confirm_boleto_payment(o, "000123") is False
