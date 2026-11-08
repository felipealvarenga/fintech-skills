"""Stripe PaymentIntent tests.

- test_create_intent_replay: runs in CI on every PR, replays a recording, no network.
- test_create_intent_contract: hits the Stripe sandbox. Runs only in the scheduled job
  (`pytest -m contract`), never on pull requests. Re-record the fixture when it passes.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import stripe

FIXTURE = Path(__file__).parent / "fixtures" / "payment_intent_create.json"
MAX_FIXTURE_AGE = timedelta(days=30)


def _load():
    return json.loads(FIXTURE.read_text())


def test_create_intent_replay(monkeypatch):
    rec = _load()
    calls = []

    def fake_create(**params):
        calls.append(params)
        return stripe.util.convert_to_stripe_object(rec["response"])

    monkeypatch.setattr(stripe.PaymentIntent, "create", fake_create)

    intent = stripe.PaymentIntent.create(amount=100, currency="usd")

    assert calls == [rec["request"]]  # request matches what was recorded
    assert intent.status == "requires_payment_method"
    assert intent.amount == 100 and isinstance(intent.amount, int)
    assert intent.currency == "usd"


def test_fixture_is_not_stale_marker():
    # Reported by the scheduled job, not a PR gate (rule 9): skipped unless asked.
    if os.environ.get("CHECK_FIXTURE_AGE") != "1":
        pytest.skip("fixture age is checked in the scheduled job only")
    recorded = datetime.fromisoformat(_load()["recorded_at"].replace("Z", "+00:00"))
    assert datetime.now(timezone.utc) - recorded < MAX_FIXTURE_AGE


@pytest.mark.contract
@pytest.mark.skipif(not os.environ.get("STRIPE_API_KEY"), reason="no sandbox key")
def test_create_intent_contract():
    stripe.api_key = os.environ["STRIPE_API_KEY"]
    rec = _load()
    intent = stripe.PaymentIntent.create(**rec["request"])
    assert intent.status == rec["response"]["status"]
    assert intent.amount == rec["response"]["amount"]
    assert intent.currency == rec["response"]["currency"]
