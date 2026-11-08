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
    reverses: str | None = None  # id of the entry this one reverses (refunds, corrections)


class Ledger:
    def __init__(self, closed_through: date | None = None):
        self.entries: list[Entry] = []
        self.closed_through = closed_through
        self._by_ref: dict[str, Entry] = {}
        self._by_id: dict[str, Entry] = {}
        self._reversed: dict[str, Entry] = {}  # original id -> reversal entry

    def post(self, entry: Entry) -> Entry:
        """The only write path. Idempotent on external_ref: a replay returns the first entry."""
        existing = self._by_ref.get(entry.external_ref)
        if existing is not None:
            return existing
        self._validate(entry)
        self.entries.append(entry)
        self._by_ref[entry.external_ref] = entry
        self._by_id[entry.id] = entry
        if entry.reverses is not None:
            self._reversed[entry.reverses] = entry
        return entry

    def _validate(self, entry: Entry) -> None:
        if not entry.external_ref:
            raise ValueError("entry needs an external_ref")
        if entry.id in self._by_id:
            raise ValueError(f"duplicate entry id {entry.id}")
        if len(entry.postings) < 2:
            raise ValueError("entry needs at least two postings")
        net: dict[str, int] = defaultdict(int)
        for p in entry.postings:
            if p.side not in ("debit", "credit"):
                raise ValueError(f"invalid side {p.side!r}")
            if not isinstance(p.amount_minor, int) or p.amount_minor <= 0:
                raise ValueError("posting amount must be a positive integer")
            net[p.currency] += p.amount_minor if p.side == "debit" else -p.amount_minor
        unbalanced = {c: n for c, n in net.items() if n != 0}
        if unbalanced:
            raise ValueError(f"entry does not balance per currency: {unbalanced}")
        if self.closed_through is not None and entry.effective_date <= self.closed_through:
            raise ValueError(f"period closed through {self.closed_through}")
        if entry.reverses is not None:
            if entry.reverses not in self._by_id:
                raise ValueError(f"unknown entry to reverse: {entry.reverses}")
            if entry.reverses in self._reversed:
                raise ValueError(f"entry {entry.reverses} is already reversed")

    def refund(self, original_ref: str, refund_ref: str, effective_date: date,
               entry_id: str | None = None) -> Entry:
        """Fully refund a captured payment by posting a reversal of the original entry.

        Every posting is mirrored on the same account with the sides swapped, so the
        refund unwinds exactly what the capture booked (receivable, fees, customer
        balance, revenue). The original is never touched. The reversal is dated
        `effective_date`, which must fall in the open period. Replaying the same
        `refund_ref` returns the first reversal; refunding an already-refunded
        payment under a new ref raises.
        """
        replay = self._by_ref.get(refund_ref)
        if replay is not None:
            return replay
        original = self._by_ref.get(original_ref)
        if original is None:
            raise ValueError(f"unknown payment {original_ref}")
        if original.reverses is not None:
            raise ValueError("cannot refund a reversal entry")
        flip = {"debit": "credit", "credit": "debit"}
        postings = tuple(
            Posting(p.account, flip[p.side], p.amount_minor, p.currency)
            for p in original.postings
        )
        return self.post(Entry(
            id=entry_id or f"refund-{original.id}",
            effective_date=effective_date,
            postings=postings,
            external_ref=refund_ref,
            reverses=original.id,
        ))

    def balance(self, account: str, currency: str) -> int:
        """Debit-minus-credit. Negate for credit-normal accounts."""
        total = 0
        for e in self.entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    total += p.amount_minor if p.side == "debit" else -p.amount_minor
        return total
