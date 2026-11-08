"""Payout amounts are already integers in minor units (BRL cents)."""
from dataclasses import dataclass, field

# 3.5% platform fee, expressed in basis points to keep the math integer-only.
PLATFORM_FEE_BPS = 350


def platform_fee(amount_minor: int) -> int:
    """Fee in minor units, rounded half up."""
    return (amount_minor * PLATFORM_FEE_BPS + 5_000) // 10_000


@dataclass
class Payout:
    id: str
    amount_minor: int
    currency: str = "BRL"
    fee_minor: int = field(init=False)

    def __post_init__(self):
        self.fee_minor = platform_fee(self.amount_minor)


def payout_batch(payouts: list[Payout]) -> int:
    return sum(p.amount_minor for p in payouts)
