"""Payout amounts are already integers in minor units (BRL cents)."""
from dataclasses import dataclass, field

# 3.5% expressed in basis points to keep the math in integers.
PLATFORM_FEE_BPS = 350


def compute_fee(amount_minor: int) -> int:
    """Platform fee in minor units, rounded half up."""
    return (amount_minor * PLATFORM_FEE_BPS + 5000) // 10000


@dataclass
class Payout:
    id: str
    amount_minor: int
    currency: str = "BRL"
    fee_minor: int = field(init=False)

    def __post_init__(self):
        self.fee_minor = compute_fee(self.amount_minor)


def payout_batch(payouts: list[Payout]) -> int:
    return sum(p.amount_minor for p in payouts)


def batch_fees(payouts: list[Payout]) -> int:
    return sum(p.fee_minor for p in payouts)
