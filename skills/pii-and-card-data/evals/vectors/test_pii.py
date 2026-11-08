"""Test vectors for pii-and-card-data.

Run against the reference: `pytest skills/pii-and-card-data`.
Run against your module:   `PII_SOLUTION=/path/to/pii.py pytest skills/pii-and-card-data`.

The module under test must expose redact, luhn_valid, luhn_check_digit, make_test_pan,
make_test_cpf, scan, mask_pan, mask_document and schema_lint as used below.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


def _load(env, name):
    path = os.environ.get(env) or str(Path(__file__).with_name("reference.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = _load("PII_SOLUTION", "pii_under_test")

PAYMENT_EVENT = {
    "event": "payment.created",
    "payment_id": "pay_123",
    "amount_minor": 1999,
    "currency": "BRL",
    "card": {"number": "4242424242424242", "cvv": "123", "brand": "visa", "last4": "4242"},
    "customer": {"id": "cus_1", "email": "ana@example.com", "cpf": "529.982.247-25", "name": "Ana"},
    "decline_code": None,
}
ALLOW = {"event", "payment_id", "amount_minor", "currency", "card.brand", "card.last4", "customer.id", "decline_code"}


def test_redaction_keeps_only_the_allowlist():
    out = m.redact(PAYMENT_EVENT, ALLOW)
    assert out == {"event": "payment.created", "payment_id": "pay_123", "amount_minor": 1999, "currency": "BRL",
                   "card": {"brand": "visa", "last4": "4242"}, "customer": {"id": "cus_1"}, "decline_code": None}


def test_redacted_log_line_contains_no_pan_cpf_or_email():
    line = json.dumps(m.redact(PAYMENT_EVENT, ALLOW))
    assert m.scan(line) == []
    raw = json.dumps(PAYMENT_EVENT)
    assert set(m.scan(raw)) == {"pan", "cpf", "email"}


def test_new_field_is_dropped_by_default():
    event = dict(PAYMENT_EVENT, bank_account="12345-6")
    assert "bank_account" not in m.redact(event, ALLOW)


@pytest.mark.parametrize("number,valid", [
    ("4242424242424242", True),
    ("4242 4242 4242 4242", True),
    ("4242424242424241", False),
    ("5555555555554444", True),
    ("378282246310005", True),
    ("1234567890123", False),
    ("4242", False),
])
def test_luhn(number, valid):
    assert m.luhn_valid(number) is valid


def test_test_pan_generator_is_valid_and_deterministic():
    a, b = m.make_test_pan(seed=7), m.make_test_pan(seed=7)
    assert a == b and len(a) == 16 and a.startswith("4242") and m.luhn_valid(a)
    assert m.make_test_pan(seed=8) != a
    assert m.luhn_check_digit("424242424242424") == 2


def test_test_cpf_generator_is_valid_and_deterministic():
    brazil = _load("BRAZIL_SOLUTION", "brazil_ref_for_pii") if False else None
    cpf = m.make_test_cpf(seed=3)
    assert cpf == m.make_test_cpf(seed=3) and len(cpf) == 11
    assert m.scan(f"doc {cpf}") == ["cpf"]  # the generator produces a valid check digit
    assert m.scan("doc 11111111111") == []


def test_scan_finds_formatted_and_spaced_numbers():
    assert "pan" in m.scan("card 4242 4242 4242 4242 declined")
    assert "pan" in m.scan("card 4242-4242-4242-4242")
    assert "cpf" in m.scan("cpf 52998224725")
    assert m.scan("order 1234567890123 total 19.99") == []  # not Luhn valid, not a CPF
    assert m.scan("evt_1 pay_123 1999 BRL visa 4242") == []


def test_masking():
    assert m.mask_pan("4242424242424242") == "************4242"
    assert m.mask_document("529.982.247-25") == "*********25"
    with pytest.raises(Exception):
        m.mask_pan("1234567890123")


@pytest.mark.parametrize("columns,flagged", [
    (["id", "card_number", "cvv", "last4", "brand"], ["card_number", "cvv"]),
    (["pan", "customer_pan", "security_code", "cvc", "track2"], ["pan", "customer_pan", "security_code", "cvc", "track2"]),
    (["id", "amount_minor", "payment_token", "expiry_month"], []),
    (["company", "panel_id", "cvvx"], []),
])
def test_schema_lint(columns, flagged):
    assert m.schema_lint(columns) == flagged
