"""Shared user wallets (Brazil + US).

Each wallet is a single USD account. BRL amounts are converted on the fly at
the given rate; the conversion is recorded as part of the entry through FX
accounts, so every entry balances per currency and the rate is kept.

Balances are derived from immutable postings. `post()` is the only write path.
Amounts are integer minor units (cents / centavos), never floats.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Callable, Optional

# Accounts: (code, normal balance)
CASH = {"USD": "cash:USD", "BRL": "cash:BRL"}  # assets, debit-normal
FX = {"USD": "fx:USD", "BRL": "fx:BRL"}        # conversion accounts
MERCHANT = {"USD": "payable:USD", "BRL": "payable:BRL"}  # liabilities, credit-normal


def wallet_account(user_id: str) -> str:
    return f"wallet:{user_id}"  # liability, credit-normal, USD only


class LedgerError(Exception):
    pass


@dataclass(frozen=True)
class Posting:
    account: str
    side: str  # "debit" | "credit"
    amount_minor: int
    currency: str


@dataclass(frozen=True)
class Entry:
    ref: str
    postings: tuple
    effective_date: date
    recorded_at: datetime
    fx_rate: Optional[Decimal] = None  # USD per 1 BRL, when a conversion happened


class Ledger:
    def __init__(self):
        self._entries: list = []
        self._by_ref: dict = {}
        self.closed_through: Optional[date] = None

    def post(self, ref, postings, effective_date=None, fx_rate=None) -> Entry:
        if not ref:
            raise LedgerError("external reference required")
        if ref in self._by_ref:
            return self._by_ref[ref]  # idempotent replay
        effective_date = effective_date or date.today()
        if self.closed_through and effective_date <= self.closed_through:
            raise LedgerError("period closed")
        postings = tuple(postings)
        if len(postings) < 2:
            raise LedgerError("entry needs at least two postings")
        totals: dict = {}
        for p in postings:
            if p.amount_minor <= 0 or p.side not in ("debit", "credit"):
                raise LedgerError("posting must be positive with a valid side")
            d, c = totals.get(p.currency, (0, 0))
            totals[p.currency] = (
                (d + p.amount_minor, c) if p.side == "debit" else (d, c + p.amount_minor)
            )
        if any(d != c for d, c in totals.values()):
            raise LedgerError("entry does not balance per currency")
        entry = Entry(ref, postings, effective_date, datetime.now(timezone.utc), fx_rate)
        self._entries.append(entry)
        self._by_ref[ref] = entry
        return entry

    def balance(self, account: str, currency: str, credit_normal: bool = False) -> int:
        net = 0
        for e in self._entries:
            for p in e.postings:
                if p.account == account and p.currency == currency:
                    net += p.amount_minor if p.side == "debit" else -p.amount_minor
        return -net if credit_normal else net


def _to_usd_minor(brl_minor: int, usd_per_brl: Decimal) -> int:
    usd = (Decimal(brl_minor) * usd_per_brl).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    if usd <= 0:
        raise LedgerError("amount too small after conversion")
    return int(usd)


def wallet_balance_usd(ledger: Ledger, user_id: str) -> int:
    """Balance in USD cents."""
    return ledger.balance(wallet_account(user_id), "USD", credit_normal=True)


def wallet_balance_brl(ledger: Ledger, user_id: str, usd_per_brl: Decimal) -> int:
    """Display-only: USD balance converted to BRL centavos at the given rate."""
    usd = Decimal(wallet_balance_usd(ledger, user_id))
    return int((usd / usd_per_brl).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def top_up(ledger: Ledger, user_id: str, amount_minor: int, currency: str, ref: str,
           usd_per_brl: Optional[Decimal] = None) -> Entry:
    w = wallet_account(user_id)
    if currency == "USD":
        return ledger.post(ref, [
            Posting(CASH["USD"], "debit", amount_minor, "USD"),
            Posting(w, "credit", amount_minor, "USD"),
        ])
    if currency == "BRL":
        if usd_per_brl is None:
            raise LedgerError("rate required for BRL")
        usd = _to_usd_minor(amount_minor, usd_per_brl)
        return ledger.post(ref, [
            Posting(CASH["BRL"], "debit", amount_minor, "BRL"),
            Posting(FX["BRL"], "credit", amount_minor, "BRL"),
            Posting(FX["USD"], "debit", usd, "USD"),
            Posting(w, "credit", usd, "USD"),
        ], fx_rate=usd_per_brl)
    raise LedgerError(f"unsupported currency {currency}")


def pay(ledger: Ledger, user_id: str, amount_minor: int, currency: str, ref: str,
        usd_per_brl: Optional[Decimal] = None) -> Entry:
    w = wallet_account(user_id)
    if currency == "USD":
        usd, postings, rate = amount_minor, [
            Posting(w, "debit", amount_minor, "USD"),
            Posting(MERCHANT["USD"], "credit", amount_minor, "USD"),
        ], None
    elif currency == "BRL":
        if usd_per_brl is None:
            raise LedgerError("rate required for BRL")
        usd = _to_usd_minor(amount_minor, usd_per_brl)
        rate = usd_per_brl
        postings = [
            Posting(w, "debit", usd, "USD"),
            Posting(FX["USD"], "credit", usd, "USD"),
            Posting(FX["BRL"], "debit", amount_minor, "BRL"),
            Posting(MERCHANT["BRL"], "credit", amount_minor, "BRL"),
        ]
    else:
        raise LedgerError(f"unsupported currency {currency}")
    if ref not in ledger._by_ref and wallet_balance_usd(ledger, user_id) < usd:
        raise LedgerError("insufficient funds")
    return ledger.post(ref, postings, fx_rate=rate)
