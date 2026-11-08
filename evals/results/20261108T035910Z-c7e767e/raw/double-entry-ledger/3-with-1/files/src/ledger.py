"""Minimal double-entry ledger. Amounts are integer minor units (cents)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable

DEBIT, CREDIT = "debit", "credit"

# code -> (name, normal balance)
CHART = {
    "1010": ("Cash at bank", DEBIT),
    "1020": ("Receivable from processor", DEBIT),
    "1030": ("In transit", DEBIT),
    "2010": ("Customer balances", CREDIT),
    "2020": ("Refunds payable", CREDIT),
    "4010": ("Revenue", CREDIT),
    "5010": ("Processor fees", DEBIT),
}


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str
    amount_minor: int
    currency: str = "USD"

    def __post_init__(self):
        if self.side not in (DEBIT, CREDIT):
            raise LedgerError(f"invalid side {self.side!r}")
        if not isinstance(self.amount_minor, int) or self.amount_minor <= 0:
            raise LedgerError("posting amount must be a positive integer")
        if self.account not in CHART:
            raise LedgerError(f"unknown account {self.account!r}")


@dataclass(frozen=True)
class Entry:
    tenant: str
    external_ref: str
    effective_date: date
    postings: tuple[Posting, ...]
    memo: str = ""
    reverses: str | None = None  # external_ref of the original
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        object.__setattr__(self, "postings", tuple(self.postings))


def _validate_balanced(postings: Iterable[Posting]) -> None:
    postings = tuple(postings)
    if len(postings) < 2:
        raise LedgerError("entry needs at least two postings")
    net: dict[str, int] = defaultdict(int)
    for p in postings:
        net[p.currency] += p.amount_minor if p.side == DEBIT else -p.amount_minor
    unbalanced = {c: v for c, v in net.items() if v != 0}
    if unbalanced:
        raise LedgerError(f"entry does not balance per currency: {unbalanced}")


class Ledger:
    def __init__(self, closed_through: date | None = None):
        self._entries: list[Entry] = []
        self._by_ref: dict[tuple[str, str], Entry] = {}
        self.closed_through = closed_through

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(self._entries)

    def post(self, entry: Entry) -> Entry:
        """The only write path. Idempotent on (tenant, external_ref)."""
        key = (entry.tenant, entry.external_ref)
        if key in self._by_ref:
            return self._by_ref[key]
        _validate_balanced(entry.postings)
        if self.closed_through and entry.effective_date <= self.closed_through:
            raise LedgerError("period is closed")
        self._entries.append(entry)
        self._by_ref[key] = entry
        return entry

    def reverse(self, tenant: str, original_ref: str, effective_date: date) -> Entry:
        orig = self._by_ref[(tenant, original_ref)]
        flipped = tuple(
            Posting(p.account, CREDIT if p.side == DEBIT else DEBIT, p.amount_minor, p.currency)
            for p in orig.postings
        )
        return self.post(Entry(tenant, f"reversal:{original_ref}", effective_date,
                               flipped, f"Reversal of {original_ref}", reverses=original_ref))

    def balance(self, tenant: str, account: str, currency: str = "USD",
                as_of: date | None = None) -> int:
        """Derived from postings; sign follows the account's normal balance."""
        total = 0
        for e in self._entries:
            if e.tenant != tenant or (as_of and e.effective_date > as_of):
                continue
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == DEBIT else -p.amount_minor
        return total if CHART[account][1] == DEBIT else -total

    def trial_balance(self, tenant: str | None = None) -> tuple[int, int]:
        d = c = 0
        for e in self._entries:
            if tenant is not None and e.tenant != tenant:
                continue
            for p in e.postings:
                if p.side == DEBIT:
                    d += p.amount_minor
                else:
                    c += p.amount_minor
        return d, c


def card_capture(tenant: str, external_ref: str, effective_date: date, *,
                 gross_minor: int, processor_fee_minor: int, our_share_minor: int,
                 currency: str = "USD") -> Entry:
    """Capture: receivable = gross - fee; fee expense; merchant owed gross - our share; revenue = our share."""
    merchant_minor = gross_minor - our_share_minor
    if merchant_minor < 0:
        raise LedgerError("our share exceeds gross")
    return Entry(tenant, external_ref, effective_date, (
        Posting("1020", DEBIT, gross_minor - processor_fee_minor, currency),
        Posting("5010", DEBIT, processor_fee_minor, currency),
        Posting("2010", CREDIT, merchant_minor, currency),
        Posting("4010", CREDIT, our_share_minor, currency),
    ), memo="Card capture")
