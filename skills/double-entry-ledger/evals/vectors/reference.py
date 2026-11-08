"""Reference ledger for the double-entry-ledger vectors.

Minimal and in-memory on purpose. It demonstrates the invariants the vectors test:
balanced entries per currency, positive postings with a side, immutability, derived balances,
reversal, period close and idempotent posting by external reference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


class Unbalanced(ValueError):
    pass


class InvalidPosting(ValueError):
    pass


class PeriodClosed(ValueError):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str  # "debit" | "credit"
    amount: int  # minor units, > 0
    currency: str


@dataclass(frozen=True)
class Entry:
    id: str
    effective_date: date
    postings: tuple[Posting, ...]
    external_ref: str
    description: str = ""
    reverses: str | None = None


def validate(entry: Entry) -> None:
    if len(entry.postings) < 2:
        raise InvalidPosting("an entry needs at least two postings")
    sums: dict[str, int] = {}
    for p in entry.postings:
        if p.side not in ("debit", "credit"):
            raise InvalidPosting(f"bad side {p.side!r}")
        if not isinstance(p.amount, int) or p.amount <= 0:
            raise InvalidPosting("posting amounts must be positive integers")
        sums[p.currency] = sums.get(p.currency, 0) + (p.amount if p.side == "debit" else -p.amount)
    for ccy, net in sums.items():
        if net != 0:
            raise Unbalanced(f"{ccy} debits and credits differ by {net}")


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)
    closed_through: date | None = None
    _by_ref: dict[str, Entry] = field(default_factory=dict)

    def post(self, entry: Entry) -> Entry:
        existing = self._by_ref.get(entry.external_ref)
        if existing is not None:
            return existing
        validate(entry)
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise PeriodClosed(f"{entry.effective_date} is on or before {self.closed_through}")
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        return entry

    def close(self, through: date) -> None:
        self.closed_through = through

    def balance(self, account: str, currency: str, as_of: date | None = None) -> int:
        """Net debit balance: debits minus credits. Credit-normal accounts read negative."""
        total = 0
        for e in self.entries:
            if as_of is not None and e.effective_date > as_of:
                continue
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount if p.side == "debit" else -p.amount
        return total

    def reverse(self, entry_id: str, on: date, new_id: str, external_ref: str) -> Entry:
        original = next(e for e in self.entries if e.id == entry_id)
        flipped = tuple(
            Posting(p.account, "credit" if p.side == "debit" else "debit", p.amount, p.currency)
            for p in original.postings
        )
        return self.post(Entry(new_id, on, flipped, external_ref,
                               f"reversal of {entry_id}", reverses=entry_id))

    def trial_balance(self) -> tuple[int, int]:
        debits = sum(p.amount for e in self.entries for p in e.postings if p.side == "debit")
        credits = sum(p.amount for e in self.entries for p in e.postings if p.side == "credit")
        return debits, credits
