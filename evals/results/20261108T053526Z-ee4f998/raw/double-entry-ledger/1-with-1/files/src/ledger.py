"""Minimal double-entry ledger. `Ledger.post` is the only write path for postings."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol

DEBIT, CREDIT = "debit", "credit"

# Chart of accounts (code, normal balance)
CASH = "1010"
CUSTOMER_PREFIX = "2010:"  # one liability account per user: "2010:<user_id>"
REVENUE = "4010"
CREDIT_NORMAL_PREFIXES = ("2", "3", "4")


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class Entry:
    external_ref: str
    effective_date: date
    postings: tuple
    recorded_at: datetime
    reverses: str | None = None
    description: str = ""


class Store(Protocol):
    def get_by_ref(self, ref: str) -> Entry | None: ...
    def closed_through(self) -> date | None: ...
    def append(self, entry: Entry) -> None: ...
    def sums(self, account: str, currency: str, as_of: date | None) -> tuple[int, int]: ...


def validate(postings, effective_date: date, closed_through: date | None) -> None:
    if len(postings) < 2:
        raise LedgerError("entry needs at least two postings")
    totals = defaultdict(lambda: [0, 0])
    for p in postings:
        if p.side not in (DEBIT, CREDIT):
            raise LedgerError(f"bad side {p.side!r}")
        if not isinstance(p.amount_minor, int) or p.amount_minor <= 0:
            raise LedgerError("posting amount must be a positive integer (minor units)")
        totals[p.currency][0 if p.side == DEBIT else 1] += p.amount_minor
    for cur, (d, c) in totals.items():
        if d != c:
            raise LedgerError(f"entry does not balance in {cur}: debits {d} != credits {c}")
    if closed_through is not None and effective_date <= closed_through:
        raise LedgerError(f"period closed through {closed_through}")


class Ledger:
    def __init__(self, store: Store):
        self.store = store

    def post(self, external_ref, postings, effective_date=None, reverses=None,
             description="") -> tuple[Entry, bool]:
        """Returns (entry, created). Replaying a ref returns the first entry, writes nothing."""
        existing = self.store.get_by_ref(external_ref)
        if existing is not None:
            return existing, False
        postings = tuple(postings)
        effective_date = effective_date or date.today()
        validate(postings, effective_date, self.store.closed_through())
        entry = Entry(external_ref, effective_date, postings,
                      datetime.now(timezone.utc), reverses, description)
        self.store.append(entry)
        return entry, True

    def reverse(self, external_ref, original_ref, effective_date=None) -> tuple[Entry, bool]:
        orig = self.store.get_by_ref(original_ref)
        if orig is None:
            raise LedgerError("unknown original entry")
        flipped = [Posting(p.account, CREDIT if p.side == DEBIT else DEBIT,
                           p.amount_minor, p.currency) for p in orig.postings]
        return self.post(external_ref, flipped, effective_date, reverses=original_ref,
                         description=f"reversal of {original_ref}")

    def balance(self, account: str, currency: str, as_of: date | None = None) -> int:
        d, c = self.store.sums(account, currency, as_of)
        credit_normal = account.startswith(CREDIT_NORMAL_PREFIXES)
        return c - d if credit_normal else d - c


class InMemoryStore:
    def __init__(self, closed_through: date | None = None):
        self._entries: list[Entry] = []
        self._refs: dict[str, Entry] = {}
        self._closed = closed_through

    def get_by_ref(self, ref):
        return self._refs.get(ref)

    def closed_through(self):
        return self._closed

    def append(self, entry):
        self._entries.append(entry)
        self._refs[entry.external_ref] = entry

    def sums(self, account, currency, as_of):
        d = c = 0
        for e in self._entries:
            if as_of and e.effective_date > as_of:
                continue
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    if p.side == DEBIT:
                        d += p.amount_minor
                    else:
                        c += p.amount_minor
        return d, c
