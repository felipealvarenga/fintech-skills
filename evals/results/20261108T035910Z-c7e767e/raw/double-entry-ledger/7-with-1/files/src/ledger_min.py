"""A minimal ledger: entries with postings. Balances are derived by summing postings."""
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


class Ledger:
    def __init__(self):
        self.entries: list[Entry] = []

    closed_through: date | None = None

    def post(self, entry: Entry) -> None:
        if self.closed_through and entry.effective_date <= self.closed_through:
            raise ValueError(
                f"period closed through {self.closed_through}; post the adjustment in the open period"
            )
        self.entries.append(entry)

    def close_period(self, through: date) -> None:
        """Lock the ledger: entries effective on or before `through` are refused."""
        if self.closed_through and through < self.closed_through:
            raise ValueError("cannot move closed_through backwards; reopening is an admin action")
        self.closed_through = through

    def balances(self, as_of: date) -> dict[tuple[str, str], int]:
        """Debit-minus-credit balance per (account, currency) for entries effective <= as_of."""
        out: dict[tuple[str, str], int] = {}
        for e in self.entries:
            if e.effective_date > as_of:
                continue
            for p in e.postings:
                k = (p.account, p.currency)
                out[k] = out.get(k, 0) + (p.amount_minor if p.side == "debit" else -p.amount_minor)
        return out

    def balance(self, account: str, currency: str) -> int:
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
