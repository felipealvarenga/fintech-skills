import stripe


def test_create_intent():
    intent = stripe.PaymentIntent.create(amount=100, currency="usd")
    assert intent.status == "requires_payment_method"
