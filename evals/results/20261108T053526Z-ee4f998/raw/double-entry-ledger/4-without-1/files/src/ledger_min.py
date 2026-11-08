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
        # Cached balance per (account, currency); debit-positive. Updated in post().
        self._balances: dict[tuple[str, str], int] = {}

    def post(self, entry: Entry) -> None:
        self.entries.append(entry)
        for p in entry.postings:
            key = (p.account, p.currency)
            delta = p.amount_minor if p.side == "debit" else -p.amount_minor
            self._balances[key] = self._balances.get(key, 0) + delta

    def balance(self, account: str, currency: str) -> int:
        return self._balances.get((account, currency), 0)

    def derive_balance(self, account: str, currency: str) -> int:
        """Slow path: sum all postings. Use to audit/rebuild the cache."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
