"""A minimal ledger: entries with postings. Balances are derived by summing postings.

Entries are immutable. Mistakes are fixed with `correct()`: a reversal of the original
entry plus a new entry with the right amounts, both linked to the original.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Posting:
    account: str
    side: str  # debit | credit
    amount_minor: int
    currency: str

    def __post_init__(self):
        if self.side not in ("debit", "credit"):
            raise ValueError(f"invalid side: {self.side!r}")
        if self.amount_minor <= 0:
            raise ValueError("posting amount must be positive")


@dataclass(frozen=True)
class Entry:
    id: str
    effective_date: date
    postings: tuple[Posting, ...]
    external_ref: str
    reverses: Optional[str] = None  # id of the entry this one reverses
    corrects: Optional[str] = None  # id of the entry this one replaces


class Ledger:
    def __init__(self, closed_through: Optional[date] = None):
        self.entries: list[Entry] = []
        self.closed_through = closed_through
        self._by_ref: dict[str, Entry] = {}
        self._by_id: dict[str, Entry] = {}

    def post(self, entry: Entry) -> Entry:
        """The only write path. Idempotent on external_ref."""
        existing = self._by_ref.get(entry.external_ref)
        if existing is not None:
            return existing
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        net: dict[str, int] = defaultdict(int)
        for p in entry.postings:
            net[p.currency] += p.amount_minor if p.side == "debit" else -p.amount_minor
        unbalanced = {c: v for c, v in net.items() if v != 0}
        if unbalanced:
            raise ValueError(f"entry not balanced per currency: {unbalanced}")
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise ValueError("effective_date is in a closed period")
        if entry.id in self._by_id:
            raise ValueError(f"duplicate entry id: {entry.id}")
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        self._by_id[entry.id] = entry
        return entry

    def reverse(self, entry_id: str, *, id: str, effective_date: date,
                external_ref: str) -> Entry:
        """Post an entry that mirrors the original with sides swapped."""
        orig = self._by_id[entry_id]
        flipped = tuple(
            Posting(p.account, "credit" if p.side == "debit" else "debit",
                    p.amount_minor, p.currency)
            for p in orig.postings
        )
        return self.post(Entry(id, effective_date, flipped, external_ref, reverses=orig.id))

    def correct(self, entry_id: str, new_postings: tuple[Posting, ...], *,
                effective_date: date, ref_prefix: str) -> tuple[Entry, Entry]:
        """Fix a wrong entry: reverse it and post the corrected one.

        Both are dated `effective_date` (must be in an open period) and reference the
        original. Re-running with the same `ref_prefix` is a no-op.
        """
        orig = self._by_id[entry_id]
        reversal = self.reverse(
            entry_id, id=f"{ref_prefix}-rev", effective_date=effective_date,
            external_ref=f"{ref_prefix}-rev",
        )
        replacement = self.post(Entry(
            f"{ref_prefix}-new", effective_date, tuple(new_postings),
            f"{ref_prefix}-new", corrects=orig.id,
        ))
        return reversal, replacement

    def balance(self, account: str, currency: str) -> int:
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
