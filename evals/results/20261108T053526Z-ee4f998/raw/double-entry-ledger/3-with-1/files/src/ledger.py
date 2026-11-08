"""Minimal append-only double-entry ledger. Amounts are integer minor units."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from collections import defaultdict

DEBIT, CREDIT = "debit", "credit"

# code -> (name, normal side)
CHART = {
    "1010": ("Cash at bank", DEBIT),
    "1020": ("Receivable from processor", DEBIT),
    "1030": ("In transit", DEBIT),
    "2010": ("Customer balances", CREDIT),
    "2020": ("Refunds payable", CREDIT),
    "4010": ("Revenue", CREDIT),
    "5010": ("Processor fees", DEBIT),
}


class LedgerError(ValueError):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str
    amount_minor: int
    currency: str = "USD"

    def __post_init__(self):
        if self.side not in (DEBIT, CREDIT):
            raise LedgerError(f"invalid side {self.side!r}")
        if not isinstance(self.amount_minor, int) or self.amount_minor <= 0:
            raise LedgerError("posting amount must be a positive integer")


@dataclass(frozen=True)
class Entry:
    tenant: str
    external_ref: str
    effective_date: date
    postings: tuple[Posting, ...]
    description: str = ""
    reverses: str | None = None  # external_ref of the original entry
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Ledger:
    def __init__(self, chart=None):
        self.chart = chart or CHART
        self._entries: list[Entry] = []
        self._by_ref: dict[tuple[str, str], Entry] = {}
        self.closed_through: dict[str, date] = {}

    @property
    def entries(self) -> tuple[Entry, ...]:
        return tuple(self._entries)

    def close_period(self, tenant: str, through: date) -> None:
        current = self.closed_through.get(tenant)
        if current and through < current:
            raise LedgerError("cannot move close date backwards; reopening is an admin action")
        self.closed_through[tenant] = through

    def post(self, tenant, external_ref, effective_date, postings,
             description="", reverses=None) -> Entry:
        """The only write path. Idempotent on (tenant, external_ref)."""
        key = (tenant, external_ref)
        if key in self._by_ref:
            return self._by_ref[key]
        postings = tuple(postings)
        if len(postings) < 2:
            raise LedgerError("an entry needs at least two postings")
        totals = defaultdict(lambda: [0, 0])
        for p in postings:
            if p.account not in self.chart:
                raise LedgerError(f"unknown account {p.account}")
            totals[p.currency][0 if p.side == DEBIT else 1] += p.amount_minor
        for cur, (d, c) in totals.items():
            if d != c:
                raise LedgerError(f"unbalanced in {cur}: debits {d} != credits {c}")
        closed = self.closed_through.get(tenant)
        if closed and effective_date <= closed:
            raise LedgerError(f"period closed through {closed}")
        entry = Entry(tenant, external_ref, effective_date, postings, description, reverses)
        self._entries.append(entry)
        self._by_ref[key] = entry
        return entry

    def reverse(self, tenant, original_ref, external_ref, effective_date) -> Entry:
        """Correct by posting the mirror image in the open period."""
        orig = self._by_ref.get((tenant, original_ref))
        if orig is None:
            raise LedgerError("unknown original entry")
        flipped = tuple(
            Posting(p.account, CREDIT if p.side == DEBIT else DEBIT, p.amount_minor, p.currency)
            for p in orig.postings
        )
        return self.post(tenant, external_ref, effective_date, flipped,
                         description=f"reversal of {original_ref}", reverses=original_ref)

    def balance(self, tenant, account, as_of: date | None = None, currency="USD") -> int:
        """Derived from postings; sign follows the account's normal balance."""
        net = 0
        for e in self._entries:
            if e.tenant != tenant or (as_of and e.effective_date > as_of):
                continue
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    net += p.amount_minor if p.side == DEBIT else -p.amount_minor
        return net if self.chart[account][1] == DEBIT else -net

    def trial_balance(self, tenant) -> tuple[int, int]:
        d = c = 0
        for e in self._entries:
            if e.tenant == tenant:
                for p in e.postings:
                    if p.side == DEBIT:
                        d += p.amount_minor
                    else:
                        c += p.amount_minor
        return d, c
