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

    def post(self, entry: Entry) -> Entry:
        existing = self.get_by_ref(entry.external_ref)
        if existing is not None:
            return existing  # idempotent replay
        self._check_valid(entry)
        self.entries.append(entry)
        return entry

    def get_by_ref(self, external_ref: str) -> Entry | None:
        for e in self.entries:
            if e.external_ref == external_ref:
                return e
        return None

    @staticmethod
    def _check_valid(entry: Entry) -> None:
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        net: dict[str, int] = {}
        for p in entry.postings:
            if p.amount_minor <= 0:
                raise ValueError("posting amount must be positive")
            if p.side not in ("debit", "credit"):
                raise ValueError("side must be debit or credit")
            net[p.currency] = net.get(p.currency, 0) + (
                p.amount_minor if p.side == "debit" else -p.amount_minor
            )
        if any(v != 0 for v in net.values()):
            raise ValueError("entry does not balance per currency")

    def reverse(self, original_id: str, reversal_id: str,
                effective_date: date, external_ref: str) -> Entry:
        """Post an entry that mirrors the original with debit/credit swapped."""
        original = next(e for e in self.entries if e.id == original_id)
        flipped = tuple(
            Posting(p.account, "credit" if p.side == "debit" else "debit",
                    p.amount_minor, p.currency)
            for p in original.postings
        )
        return self.post(Entry(reversal_id, effective_date, flipped, external_ref))

    def correct(self, original_id: str, corrected_postings: tuple[Posting, ...],
                effective_date: date, ref_prefix: str) -> tuple[Entry, Entry]:
        """Fix a wrong entry: reverse it, then post the corrected one.

        The original is never modified. Use an effective_date in the open period.
        """
        reversal = self.reverse(original_id, f"{original_id}-rev", effective_date,
                                f"{ref_prefix}:reversal")
        replacement = self.post(Entry(f"{original_id}-fix", effective_date,
                                      corrected_postings, f"{ref_prefix}:correction"))
        return reversal, replacement

    def balance(self, account: str, currency: str) -> int:
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
