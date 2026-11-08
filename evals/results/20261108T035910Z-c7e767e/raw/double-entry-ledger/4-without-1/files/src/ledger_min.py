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
        # Cached running balance per (account, currency), updated on every post.
        self._balances: dict[tuple[str, str], int] = {}

    def post(self, entry: Entry) -> None:
        # Compute deltas first so the cache and entries change together.
        deltas: dict[tuple[str, str], int] = {}
        for p in entry.postings:
            key = (p.account, p.currency)
            deltas[key] = deltas.get(key, 0) + (
                p.amount_minor if p.side == "debit" else -p.amount_minor
            )
        self.entries.append(entry)
        for key, delta in deltas.items():
            self._balances[key] = self._balances.get(key, 0) + delta

    def balance(self, account: str, currency: str) -> int:
        return self._balances.get((account, currency), 0)

    def recompute_balance(self, account: str, currency: str) -> int:
        """Slow path: derive the balance by summing postings. For audits/reconciliation."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
