"""A minimal ledger: entries with postings. Balances are derived by summing postings."""
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


@dataclass(frozen=True)
class Entry:
    id: str
    effective_date: date
    postings: tuple[Posting, ...]
    external_ref: str
    reverses: Optional[str] = None  # id of the entry this one reverses (refunds)


class Ledger:
    def __init__(self, closed_through: Optional[date] = None):
        self.entries: list[Entry] = []
        self.closed_through = closed_through
        self._by_ref: dict[str, Entry] = {}
        self._by_id: dict[str, Entry] = {}
        self._reversed: set[str] = set()

    def post(self, entry: Entry) -> Entry:
        """The only write path. Idempotent on external_ref."""
        existing = self._by_ref.get(entry.external_ref)
        if existing is not None:
            return existing
        if entry.id in self._by_id:
            raise ValueError(f"duplicate entry id {entry.id}")
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise ValueError("effective_date is in a closed period")
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        totals: dict[str, int] = defaultdict(int)
        for p in entry.postings:
            if p.side not in ("debit", "credit"):
                raise ValueError(f"invalid side {p.side!r}")
            if p.amount_minor <= 0:
                raise ValueError("posting amount must be positive")
            totals[p.currency] += p.amount_minor if p.side == "debit" else -p.amount_minor
        if any(t != 0 for t in totals.values()):
            raise ValueError("entry does not balance per currency")
        if entry.reverses is not None:
            if entry.reverses not in self._by_id:
                raise ValueError("reversed entry not found")
            if entry.reverses in self._reversed:
                raise ValueError("entry already reversed")
            self._reversed.add(entry.reverses)
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        self._by_id[entry.id] = entry
        return entry

    def refund(self, original_id: str, refund_id: str, effective_date: date,
               external_ref: str) -> Entry:
        """Fully refund a captured payment by posting a reversal of the original entry.

        Every posting is mirrored (debit <-> credit) through the same accounts the
        payment used, so the original is never edited. `effective_date` is when the
        refund belongs in the books (must be in an open period, not the capture date).
        `external_ref` is the processor refund id; replaying it returns the first entry.
        """
        existing = self._by_ref.get(external_ref)
        if existing is not None:
            return existing
        original = self._by_id.get(original_id)
        if original is None:
            raise ValueError(f"unknown entry {original_id}")
        if original.reverses is not None:
            raise ValueError("cannot refund a reversal entry")
        flipped = tuple(
            Posting(p.account, "credit" if p.side == "debit" else "debit",
                    p.amount_minor, p.currency)
            for p in original.postings
        )
        return self.post(Entry(refund_id, effective_date, flipped, external_ref,
                               reverses=original_id))

    def balance(self, account: str, currency: str) -> int:
        """Debit-minus-credit balance (positive = net debit)."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
