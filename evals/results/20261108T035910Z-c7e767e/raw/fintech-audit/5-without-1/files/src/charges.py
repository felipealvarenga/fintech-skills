"""POST /charges."""
from decimal import Decimal
import stripe

PLATFORM_FEE_RATE = Decimal("0.035")


def platform_fee_cents(amount_cents: int) -> int:
    return int((Decimal(amount_cents) * PLATFORM_FEE_RATE).to_integral_value())


def create_charge(order):
    # Deterministic key: retries of the same order must not create a second charge.
    intent = stripe.PaymentIntent.create(
        amount=order.amount_cents, currency="brl",
        idempotency_key=f"charge-{order.id}",
    )
    return intent
