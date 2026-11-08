"""POST /charges."""
from decimal import Decimal, ROUND_HALF_EVEN
import stripe

PLATFORM_FEE_RATE = Decimal("0.035")


def platform_fee_cents(amount_cents: int) -> int:
    return int((Decimal(amount_cents) * PLATFORM_FEE_RATE).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def create_charge(order):
    # Key derived from the order: a retry after a timeout reuses it, so one charge at most.
    intent = stripe.PaymentIntent.create(
        amount=order.amount_cents, currency="brl",
        idempotency_key=f"charge:{order.id}",
    )
    return intent
