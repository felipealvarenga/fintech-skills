"""User wallets (Brazil and US users share this one model).

The wallet is a USD liability account per user. BRL amounts are converted to USD
when the movement happens, as a balanced two-currency entry through FX accounts,
with the rate stored on the entry. BRL is only converted on the fly for display.
`rate` is USD per 1 BRL and must come from the caller's rate provider.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN

from ledger import Ledger, LedgerError, Posting

CASH = {"USD": "cash:USD", "BRL": "cash:BRL"}
PAYABLE = {"USD": "merchant_payable:USD", "BRL": "merchant_payable:BRL"}


def setup(ledger: Ledger) -> None:
    for cur in ("USD", "BRL"):
        ledger.open_account(CASH[cur], cur, "debit")
        ledger.open_account(PAYABLE[cur], cur, "credit")
        ledger.open_account(f"fx:{cur}", cur, "debit")


def wallet_account(ledger: Ledger, user_id: str) -> str:
    name = f"wallet:{user_id}:USD"
    ledger.open_account(name, "USD", "credit")
    return name


def to_usd_minor(amount_minor: int, rate: Decimal) -> int:
    return int((Decimal(amount_minor) * rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def top_up(ledger: Ledger, user_id: str, amount_minor: int, currency: str, ref: str,
           effective_date: date, rate: Decimal | None = None):
    w = wallet_account(ledger, user_id)
    if currency == "USD":
        return ledger.post(ref, [Posting(CASH["USD"], "debit", amount_minor),
                                 Posting(w, "credit", amount_minor)], effective_date)
    usd = _convert(amount_minor, currency, rate)
    return ledger.post(ref, [
        Posting(CASH["BRL"], "debit", amount_minor), Posting("fx:BRL", "credit", amount_minor),
        Posting("fx:USD", "debit", usd), Posting(w, "credit", usd),
    ], effective_date, rate)


def pay(ledger: Ledger, user_id: str, amount_minor: int, currency: str, ref: str,
        effective_date: date, rate: Decimal | None = None):
    w = wallet_account(ledger, user_id)
    if currency == "USD":
        usd, postings, used_rate = amount_minor, [
            Posting(w, "debit", amount_minor), Posting(PAYABLE["USD"], "credit", amount_minor)], None
    else:
        usd = _convert(amount_minor, currency, rate)
        postings, used_rate = [
            Posting(w, "debit", usd), Posting("fx:USD", "credit", usd),
            Posting("fx:BRL", "debit", amount_minor), Posting(PAYABLE["BRL"], "credit", amount_minor),
        ], rate
    if ref not in {e.external_ref for e in ledger.entries} and ledger.balance(w) < usd:
        raise LedgerError("insufficient funds")
    return ledger.post(ref, postings, effective_date, used_rate)


def balance_usd(ledger: Ledger, user_id: str) -> int:
    return ledger.balance(wallet_account(ledger, user_id))


def balance_display(ledger: Ledger, user_id: str, currency: str, rate: Decimal | None = None) -> int:
    """On-the-fly display conversion only; never stored."""
    usd = balance_usd(ledger, user_id)
    if currency == "USD":
        return usd
    if not rate:
        raise LedgerError("rate required")
    return int((Decimal(usd) / rate).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _convert(amount_minor: int, currency: str, rate: Decimal | None) -> int:
    if currency != "BRL":
        raise LedgerError(f"unsupported currency {currency}")
    if not rate or rate <= 0:
        raise LedgerError("positive rate required for BRL")
    return to_usd_minor(amount_minor, rate)
