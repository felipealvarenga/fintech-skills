"""POST /charges."""
import uuid
import stripe

PLATFORM_FEE_RATE = 0.035


def create_charge(order):
    intent = stripe.PaymentIntent.create(
        amount=order.amount_cents, currency="brl",
        idempotency_key=str(uuid.uuid4()),
    )
    return intent
