"""A minimal ledger: entries with postings. Balances are derived by summing postings."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date


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


class PeriodClosedError(ValueError):
    pass


class Ledger:
    def __init__(self):
        self.entries: list[Entry] = []
        self.closed_through: date | None = None
        self._by_ref: dict[str, Entry] = {}

    def post(self, entry: Entry) -> Entry:
        # Idempotent replay: same external ref returns the first entry, writes nothing.
        if entry.external_ref in self._by_ref:
            return self._by_ref[entry.external_ref]
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        sums: dict[str, int] = defaultdict(int)
        for p in entry.postings:
            if p.amount_minor <= 0:
                raise ValueError("posting amount must be positive")
            if p.side not in ("debit", "credit"):
                raise ValueError("side must be debit or credit")
            sums[p.currency] += p.amount_minor if p.side == "debit" else -p.amount_minor
        if any(v != 0 for v in sums.values()):
            raise ValueError("entry does not balance per currency")
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise PeriodClosedError(
                f"period closed through {self.closed_through}; post the adjustment in the open period"
            )
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        return entry

    def balance(self, account: str, currency: str, as_of: date | None = None) -> int:
        """Debit-minus-credit balance (positive = net debit), optionally as of a date inclusive."""
        total = 0
        for e in self.entries:
            if as_of is not None and e.effective_date > as_of:
                continue
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total

    def balances(self, as_of: date | None = None) -> dict[tuple[str, str], int]:
        """Balance per (account, currency) as of a date."""
        out: dict[tuple[str, str], int] = defaultdict(int)
        for e in self.entries:
            if as_of is not None and e.effective_date > as_of:
                continue
            for p in e.postings:
                out[(p.account, p.currency)] += p.amount_minor if p.side == "debit" else -p.amount_minor
        return dict(out)

    def close_period(self, through: date) -> None:
        """Lock the ledger: entries effective on or before `through` are refused."""
        if self.closed_through is not None and through < self.closed_through:
            raise ValueError("reopening a period is an administrative action, not close_period")
        self.closed_through = through
