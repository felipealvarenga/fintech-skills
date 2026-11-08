"""Contract test against the Stripe sandbox.

Run on a schedule only (`pytest -m contract`), never in the PR gate.
Register the marker in pytest.ini: markers = contract: hits the Stripe sandbox
"""
import os

import pytest
import stripe

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(not os.environ.get("STRIPE_API_KEY"), reason="no sandbox key"),
]


def test_create_intent():
    stripe.api_key = os.environ["STRIPE_API_KEY"]
    intent = stripe.PaymentIntent.create(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"
    assert intent.amount == 100
    assert intent.currency == "usd"
