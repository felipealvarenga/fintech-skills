import os
from unittest import mock

import pytest
import stripe


def test_create_intent():
    """Unit test: Stripe is mocked, so no network and no flakiness."""
    fake = stripe.PaymentIntent.construct_from(
        {"id": "pi_test_123", "amount": 100, "currency": "usd",
         "status": "requires_payment_method"},
        "sk_test_fake",
    )
    with mock.patch.object(stripe.PaymentIntent, "create", return_value=fake) as create:
        intent = stripe.PaymentIntent.create(amount=100, currency="usd")

    create.assert_called_once_with(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"


@pytest.mark.skipif(
    not os.environ.get("STRIPE_LIVE_TESTS"),
    reason="Hits the Stripe sandbox; set STRIPE_LIVE_TESTS=1 (and stripe.api_key) to run",
)
def test_create_intent_live():
    intent = stripe.PaymentIntent.create(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"
