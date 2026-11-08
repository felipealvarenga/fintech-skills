"""A minimal ledger: entries with postings.

Postings are the source of truth. `balance()` reads a cached per-account balance that
`post()` updates in the same step; `derived_balance()` recomputes it from postings, and
`reconcile()` / `rebuild_cache()` detect and repair drift.
Convention: balance = sum(debits) - sum(credits).
"""
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


def _signed(p: Posting) -> int:
    return p.amount_minor if p.side == "debit" else -p.amount_minor


class Ledger:
    def __init__(self, closed_through: date | None = None):
        self.entries: list[Entry] = []
        self.closed_through = closed_through
        self._by_ref: dict[str, Entry] = {}
        self._cache: dict[tuple[str, str], int] = {}

    def _validate(self, entry: Entry) -> None:
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        per_ccy: dict[str, int] = {}
        for p in entry.postings:
            if p.side not in ("debit", "credit"):
                raise ValueError(f"bad side: {p.side!r}")
            if p.amount_minor <= 0:
                raise ValueError("posting amount must be positive")
            per_ccy[p.currency] = per_ccy.get(p.currency, 0) + _signed(p)
        if any(v != 0 for v in per_ccy.values()):
            raise ValueError("entry does not balance per currency")
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise ValueError("period is closed")

    def post(self, entry: Entry) -> Entry:
        """The only write path. Idempotent on external_ref."""
        existing = self._by_ref.get(entry.external_ref)
        if existing is not None:
            return existing
        self._validate(entry)
        # Validation passed: append and update the cache together.
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        for p in entry.postings:
            key = (p.account, p.currency)
            self._cache[key] = self._cache.get(key, 0) + _signed(p)
        return entry

    def balance(self, account: str, currency: str) -> int:
        """O(1) read from the cache."""
        return self._cache.get((account, currency), 0)

    def derived_balance(self, account: str, currency: str) -> int:
        """Source-of-truth balance, summed from postings (slow)."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += _signed(p)
        return total

    def _derive_all(self) -> dict[tuple[str, str], int]:
        out: dict[tuple[str, str], int] = {}
        for e in self.entries:
            for p in e.postings:
                key = (p.account, p.currency)
                out[key] = out.get(key, 0) + _signed(p)
        return out

    def reconcile(self) -> list[tuple[str, str, int, int]]:
        """Return (account, currency, cached, derived) for every mismatch. Alert if non-empty."""
        derived = self._derive_all()
        return [
            (k[0], k[1], self._cache.get(k, 0), derived.get(k, 0))
            for k in sorted(set(derived) | set(self._cache))
            if self._cache.get(k, 0) != derived.get(k, 0)
        ]

    def rebuild_cache(self) -> None:
        self._cache = self._derive_all()
