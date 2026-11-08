import os
from unittest.mock import MagicMock, patch

import pytest
import stripe


def test_create_intent():
    fake_intent = MagicMock(status="requires_payment_method")
    with patch.object(stripe.PaymentIntent, "create", return_value=fake_intent) as create:
        intent = stripe.PaymentIntent.create(amount=100, currency="usd")

    create.assert_called_once_with(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"


@pytest.mark.skipif(
    not os.environ.get("STRIPE_LIVE_TESTS"),
    reason="Set STRIPE_LIVE_TESTS=1 (and stripe.api_key) to hit the Stripe sandbox",
)
def test_create_intent_live():
    intent = stripe.PaymentIntent.create(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"
