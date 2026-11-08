"""Replay test: runs in CI, never touches the Stripe sandbox."""
import json
from pathlib import Path

import stripe

FIXTURE = Path(__file__).parent / "fixtures" / "payment_intent_create.json"


def test_create_intent_replay(monkeypatch):
    rec = json.loads(FIXTURE.read_text())
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return rec["response"]

    monkeypatch.setattr(stripe.PaymentIntent, "create", fake_create)

    intent = stripe.PaymentIntent.create(amount=100, currency="usd")

    assert calls == [rec["request"]]
    assert intent["status"] == "requires_payment_method"
    assert intent["amount"] == 100 and isinstance(intent["amount"], int)
    assert intent["currency"] == "usd"
