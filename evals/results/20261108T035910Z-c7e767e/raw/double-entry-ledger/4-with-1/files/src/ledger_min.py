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
        # Cache of debit-minus-credit per (account, currency). Derived data:
        # the postings are the source of truth; see derive_balance/reconcile.
        self._balances: dict[tuple[str, str], int] = {}

    @staticmethod
    def _signed(p: Posting) -> int:
        return p.amount_minor if p.side == "debit" else -p.amount_minor

    def post(self, entry: Entry) -> None:
        # Compute deltas first so the entry and the cache change together.
        deltas: dict[tuple[str, str], int] = {}
        for p in entry.postings:
            key = (p.account, p.currency)
            deltas[key] = deltas.get(key, 0) + self._signed(p)
        self.entries.append(entry)
        for key, d in deltas.items():
            self._balances[key] = self._balances.get(key, 0) + d

    def balance(self, account: str, currency: str) -> int:
        """O(1) read of the cached balance."""
        return self._balances.get((account, currency), 0)

    def derive_balance(self, account: str, currency: str) -> int:
        """Source of truth: sum every posting. Slow; use for reconcile/rebuild."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += self._signed(p)
        return total

    def _derive_all(self) -> dict[tuple[str, str], int]:
        out: dict[tuple[str, str], int] = {}
        for e in self.entries:
            for p in e.postings:
                key = (p.account, p.currency)
                out[key] = out.get(key, 0) + self._signed(p)
        return out

    def reconcile(self) -> dict[tuple[str, str], tuple[int, int]]:
        """Compare cache with derived balances in one pass.

        Returns {(account, currency): (cached, derived)} for every mismatch;
        empty means no drift. Alert on a non-empty result.
        """
        derived = self._derive_all()
        drift = {}
        for key in derived.keys() | self._balances.keys():
            c, d = self._balances.get(key, 0), derived.get(key, 0)
            if c != d:
                drift[key] = (c, d)
        return drift

    def rebuild_balances(self) -> None:
        """Replace the cache with values derived from postings."""
        self._balances = self._derive_all()
