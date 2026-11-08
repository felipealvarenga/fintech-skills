"""POST /charges."""
from decimal import Decimal, ROUND_HALF_EVEN
import stripe

PLATFORM_FEE_BPS = 350  # 3.50%, basis points, never a float


def platform_fee_cents(amount_cents: int) -> int:
    """Fee rounded half-even once, at this single point."""
    fee = Decimal(amount_cents) * PLATFORM_FEE_BPS / Decimal(10_000)
    return int(fee.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def charge_idempotency_key(order) -> str:
    """Stable per order: a retry or timeout replay reuses the same key."""
    return f"charge-order-{order.id}"


def create_charge(order):
    return stripe.PaymentIntent.create(
        amount=order.amount_cents,
        currency="brl",
        idempotency_key=charge_idempotency_key(order),
    )
