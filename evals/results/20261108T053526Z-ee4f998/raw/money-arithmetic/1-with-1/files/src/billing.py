"""Invoice splitting on integer minor units (replaces the float path in billing_float.py)."""
from __future__ import annotations

from dataclasses import dataclass, field

from money import Money, to_minor


@dataclass(frozen=True)
class PartnerShare:
    invoice_id: str
    partner: str
    amount_minor: int  # integer minor units, never a float
    currency: str


@dataclass
class ShareStore:
    """In-memory store. Swap for a DB table with `amount_minor BIGINT` and `currency CHAR(3)`."""
    shares: list[PartnerShare] = field(default_factory=list)

    def save(self, share: PartnerShare) -> None:
        self.shares.append(share)


def split_invoice(invoice_id: str, total: Money, partners: dict[str, str],
                  store: ShareStore) -> list[PartnerShare]:
    """Split `total` between partners by ratio (decimal strings) and store each share.

    The shares always sum to the total; no rounding is involved.
    """
    names = list(partners)
    parts = total.allocate([partners[n] for n in names])
    shares = [PartnerShare(invoice_id, n, p.minor, p.currency) for n, p in zip(names, parts)]
    for s in shares:
        store.save(s)
    return shares


def split_100_brl_50_30_20(store: ShareStore, invoice_id: str = "INV-1") -> list[PartnerShare]:
    """R$ 100,00 between three partners, 50/30/20 -> 5000, 3000, 2000 minor units."""
    total = Money(to_minor("100.00", "BRL"), "BRL")
    return split_invoice(invoice_id, total, {"A": "50", "B": "30", "C": "20"}, store)
