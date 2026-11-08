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

    def post(self, entry: Entry) -> None:
        self.entries.append(entry)

    def _find(self, entry_id: str) -> Entry:
        for e in self.entries:
            if e.id == entry_id:
                return e
        raise KeyError(f"unknown entry: {entry_id}")

    @staticmethod
    def _total(entry: Entry) -> int:
        """Entry size = sum of debit amounts (equals credits for a balanced entry)."""
        return sum(p.amount_minor for p in entry.postings if p.side == "debit")

    def refund(self, original_id: str, amount_minor: int, refund_id: str,
               effective_date: date, external_ref: str) -> Entry:
        """Post a (possibly partial) refund reversing a previously posted entry.

        Each posting of the original is mirrored with sides swapped, scaled by
        amount_minor / original total. Rounding remainders go to the last posting
        on each side so the refund entry always balances exactly.
        Idempotent on external_ref: a repeat returns the existing entry.
        Raises ValueError if the cumulative refunds would exceed the original.
        """
        for e in self.entries:
            if e.external_ref == external_ref:
                return e  # retry of an already-processed refund
        if amount_minor <= 0:
            raise ValueError("refund amount must be positive")
        original = self._find(original_id)
        total = self._total(original)
        if total <= 0:
            raise ValueError("original entry has nothing to refund")

        already = sum(self._total(e) for e in self.entries
                      if e.id.startswith(f"{original_id}:refund:"))
        if already + amount_minor > total:
            raise ValueError(
                f"refund exceeds original: {already} already refunded + "
                f"{amount_minor} > {total}")

        # Scale per side so each side sums to exactly amount_minor.
        postings: list[Posting] = []
        for side in ("debit", "credit"):
            src = [p for p in original.postings if p.side == side]
            allocated = 0
            for i, p in enumerate(src):
                if i == len(src) - 1:
                    share = amount_minor - allocated
                else:
                    share = p.amount_minor * amount_minor // total
                    allocated += share
                if share:
                    postings.append(Posting(
                        p.account,
                        "credit" if side == "debit" else "debit",
                        share, p.currency))

        entry = Entry(f"{original_id}:refund:{refund_id}", effective_date,
                      tuple(postings), external_ref)
        self.post(entry)
        return entry

    def balance(self, account: str, currency: str) -> int:
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
