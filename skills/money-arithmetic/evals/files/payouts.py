"""Payout amounts are already integers in minor units (BRL cents)."""
from dataclasses import dataclass


@dataclass
class Payout:
    id: str
    amount_minor: int
    currency: str = "BRL"


def payout_batch(payouts: list[Payout]) -> int:
    return sum(p.amount_minor for p in payouts)
