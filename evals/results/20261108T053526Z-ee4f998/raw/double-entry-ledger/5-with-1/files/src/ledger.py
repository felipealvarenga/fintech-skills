"""Append-only double-entry ledger. The only write path is Ledger.post()."""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from itertools import count


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str  # "debit" | "credit"
    amount_minor: int  # always > 0


@dataclass(frozen=True)
class Entry:
    id: int
    external_ref: str
    effective_date: date
    recorded_at: datetime
    postings: tuple
    rate: Decimal | None = None  # FX rate used, USD per 1 BRL
    reverses: int | None = None


class Ledger:
    def __init__(self):
        self._accounts: dict[str, tuple[str, str]] = {}  # name -> (currency, normal side)
        self._entries: list[Entry] = []
        self._by_ref: dict[str, Entry] = {}
        self._ids = count(1)
        self.closed_through: date | None = None

    def open_account(self, name: str, currency: str, normal: str) -> None:
        if normal not in ("debit", "credit"):
            raise LedgerError("normal must be debit or credit")
        existing = self._accounts.get(name)
        if existing and existing != (currency, normal):
            raise LedgerError(f"account {name} already open with different terms")
        self._accounts[name] = (currency, normal)

    @property
    def entries(self) -> tuple:
        return tuple(self._entries)

    def post(self, external_ref: str, postings: list, effective_date: date,
             rate: Decimal | None = None, reverses: int | None = None) -> Entry:
        if external_ref in self._by_ref:  # idempotent replay
            return self._by_ref[external_ref]
        if len(postings) < 2:
            raise LedgerError("entry needs at least two postings")
        if self.closed_through and effective_date <= self.closed_through:
            raise LedgerError("period is closed")
        totals: dict[str, int] = {}
        for p in postings:
            if p.side not in ("debit", "credit"):
                raise LedgerError("bad side")
            if p.amount_minor <= 0:
                raise LedgerError("posting amount must be positive")
            if p.account not in self._accounts:
                raise LedgerError(f"unknown account {p.account}")
            cur = self._accounts[p.account][0]
            totals[cur] = totals.get(cur, 0) + (p.amount_minor if p.side == "debit" else -p.amount_minor)
        if any(v != 0 for v in totals.values()):
            raise LedgerError(f"entry does not balance per currency: {totals}")
        entry = Entry(next(self._ids), external_ref, effective_date,
                      datetime.now(timezone.utc), tuple(postings), rate, reverses)
        self._entries.append(entry)
        self._by_ref[external_ref] = entry
        return entry

    def reverse(self, entry_id: int, external_ref: str, effective_date: date) -> Entry:
        original = next((e for e in self._entries if e.id == entry_id), None)
        if original is None:
            raise LedgerError("unknown entry")
        flipped = [Posting(p.account, "credit" if p.side == "debit" else "debit", p.amount_minor)
                   for p in original.postings]
        return self.post(external_ref, flipped, effective_date, original.rate, reverses=entry_id)

    def balance(self, account: str, as_of: date | None = None) -> int:
        """Derived from postings, in the account's own currency (minor units)."""
        _, normal = self._accounts[account]
        total = 0
        for e in self._entries:
            if as_of and e.effective_date > as_of:
                continue
            for p in e.postings:
                if p.account == account:
                    total += p.amount_minor if p.side == normal else -p.amount_minor
        return total
