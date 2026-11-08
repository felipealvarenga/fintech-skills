"""User wallets.

The source of truth is the ledger (see ledger.py). users.balance_minor is a cache,
updated in the same transaction as the entry and checked by reconcile().
Call these inside a transaction. Amounts are integer minor units (e.g. cents).

Accounts: 2010 customer wallet (liability, credit-normal, per user),
          4010 revenue (credit-normal), 1020 receivable from processor (debit-normal).
"""
from datetime import date

from ledger import LedgerError, balance, post

DEBIT, CREDIT = "debit", "credit"


class InsufficientFunds(LedgerError):
    pass


def _account(db, code: str, user_id, currency: str) -> int:
    row = db.execute(
        "SELECT id FROM ledger_accounts WHERE code = %s AND user_id IS NOT DISTINCT FROM %s AND currency = %s",
        (code, user_id, currency),
    ).fetchone()
    if row is None:
        raise LedgerError(f"missing account {code} for {user_id!r} in {currency}")
    return row[0]


def pay(db, user_id: str, amount_minor: int, external_ref: str, currency: str = "BRL",
        effective_date: date | None = None) -> int:
    """Debit the user's wallet (liability falls), credit revenue. Idempotent on external_ref."""
    effective_date = effective_date or date.today()
    wallet = _account(db, "2010", user_id, currency)
    revenue = _account(db, "4010", None, currency)
    # Row lock serialises concurrent payments for this user; the conditional UPDATE guards overdraft.
    seen = db.execute("SELECT id FROM ledger_entries WHERE external_ref = %s", (external_ref,)).fetchone()
    if seen:
        return seen[0]
    cur = db.execute(
        "UPDATE users SET balance_minor = balance_minor - %s WHERE id = %s AND balance_minor >= %s",
        (amount_minor, user_id, amount_minor),
    )
    if cur.rowcount != 1:
        raise InsufficientFunds(f"user {user_id} cannot pay {amount_minor}")
    return post(db, external_ref, effective_date, [
        (wallet, DEBIT, amount_minor, currency),
        (revenue, CREDIT, amount_minor, currency),
    ])


def top_up(db, user_id: str, amount_minor: int, external_ref: str, currency: str = "BRL",
           effective_date: date | None = None) -> int:
    """Debit receivable from processor, credit the user's wallet. Idempotent on external_ref."""
    effective_date = effective_date or date.today()
    wallet = _account(db, "2010", user_id, currency)
    receivable = _account(db, "1020", None, currency)
    seen = db.execute("SELECT id FROM ledger_entries WHERE external_ref = %s", (external_ref,)).fetchone()
    if seen:
        return seen[0]
    entry = post(db, external_ref, effective_date, [
        (receivable, DEBIT, amount_minor, currency),
        (wallet, CREDIT, amount_minor, currency),
    ])
    db.execute("UPDATE users SET balance_minor = balance_minor + %s WHERE id = %s", (amount_minor, user_id))
    return entry


def reconcile(db, user_id: str, currency: str = "BRL") -> int:
    """Compare the cached column with the ledger. Returns drift (cache - derived); 0 means healthy.
    Alert on non-zero; repair by posting an adjustment, never by editing history."""
    derived = balance(db, _account(db, "2010", user_id, currency))
    cached = db.execute("SELECT balance_minor FROM users WHERE id = %s", (user_id,)).fetchone()[0]
    return cached - derived
