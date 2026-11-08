"""Payout amounts are already integers in minor units (BRL cents)."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN

PLATFORM_FEE_RATE = Decimal("0.035")  # 3.5%, from a string, never a float
FEE_ROUNDING = ROUND_HALF_EVEN  # the single rounding point for fees


@dataclass
class Payout:
    id: str
    amount_minor: int
    currency: str = "BRL"
    fee_minor: int = 0


def compute_fee(amount_minor: int) -> int:
    """Platform fee in minor units, rounded once with FEE_ROUNDING."""
    fee = Decimal(amount_minor) * PLATFORM_FEE_RATE
    return int(fee.quantize(Decimal(1), rounding=FEE_ROUNDING))


def apply_platform_fee(payout: Payout) -> Payout:
    """Store the fee on the payout; amount_minor stays the gross amount."""
    payout.fee_minor = compute_fee(payout.amount_minor)
    return payout


def payout_batch(payouts: list[Payout]) -> int:
    return sum(p.amount_minor for p in payouts)


def fee_batch(payouts: list[Payout]) -> int:
    return sum(p.fee_minor for p in payouts)
