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
    refund_of: str | None = None  # id of the entry this entry refunds


class RefundError(ValueError):
    pass


class Ledger:
    def __init__(self):
        self.entries: list[Entry] = []

    def post(self, entry: Entry) -> None:
        self.entries.append(entry)

    def get(self, entry_id: str) -> Entry:
        for e in self.entries:
            if e.id == entry_id:
                return e
        raise RefundError(f"unknown entry: {entry_id}")

    def refunded_minor(self, entry_id: str) -> int:
        """Total amount already refunded against an entry (in its single currency)."""
        total = 0
        for e in self.entries:
            if e.refund_of == entry_id:
                total += sum(p.amount_minor for p in e.postings if p.side == "debit")
        return total

    def refund(
        self,
        original_id: str,
        refund_id: str,
        external_ref: str,
        effective_date: date,
        amount_minor: int | None = None,
    ) -> Entry:
        """Refund a captured payment by posting a new entry that reverses the
        original's postings (sides swapped). The original is never mutated.

        amount_minor=None refunds the full remaining amount. Partial refunds are
        supported for simple two-posting entries (one debit, one credit, equal
        amounts). Re-submitting the same external_ref returns the existing refund
        (idempotent). Over-refunding raises RefundError.
        """
        # Idempotency: same external_ref already processed for this original.
        for e in self.entries:
            if e.refund_of == original_id and e.external_ref == external_ref:
                return e
        if any(e.id == refund_id for e in self.entries):
            raise RefundError(f"entry id already exists: {refund_id}")

        original = self.get(original_id)
        if original.refund_of is not None:
            raise RefundError("cannot refund a refund entry")

        debits = [p for p in original.postings if p.side == "debit"]
        credits = [p for p in original.postings if p.side == "credit"]
        total = sum(p.amount_minor for p in debits)
        if total != sum(p.amount_minor for p in credits):
            raise RefundError("original entry is unbalanced")
        if len({p.currency for p in original.postings}) != 1:
            raise RefundError("multi-currency refunds are not supported")

        remaining = total - self.refunded_minor(original_id)
        if amount_minor is None:
            amount_minor = remaining
        if amount_minor <= 0:
            raise RefundError("refund amount must be positive")
        if amount_minor > remaining:
            raise RefundError(
                f"refund {amount_minor} exceeds refundable amount {remaining}"
            )

        if amount_minor == total:
            postings = tuple(
                Posting(p.account, "credit" if p.side == "debit" else "debit",
                        p.amount_minor, p.currency)
                for p in original.postings
            )
        elif len(debits) == 1 and len(credits) == 1:
            postings = tuple(
                Posting(p.account, "credit" if p.side == "debit" else "debit",
                        amount_minor, p.currency)
                for p in original.postings
            )
        else:
            raise RefundError(
                "partial refund only supported for single debit/credit entries"
            )

        entry = Entry(refund_id, effective_date, postings, external_ref,
                      refund_of=original_id)
        self.post(entry)
        return entry

    def balance(self, account: str, currency: str) -> int:
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
