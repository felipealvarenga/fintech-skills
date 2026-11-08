"""User wallets.

`users.balance_minor` is a CACHE of the ledger balance of the user's wallet account
(2010:<user_id>, credit-normal liability). Every movement is a balanced journal entry;
the cache is updated in the same transaction only when a new entry was actually posted.
Use `reconcile` to detect drift and `rebuild_cache` to repair it from the ledger.
"""
from ledger import CASH, CUSTOMER_PREFIX, CREDIT, DEBIT, REVENUE, Ledger, LedgerError, Posting
from ledger_sql import SqlStore


def wallet_account(user_id: str) -> str:
    return f"{CUSTOMER_PREFIX}{user_id}"


def _ledger(db) -> Ledger:
    return Ledger(SqlStore(db))


def _apply_cache(db, user_id: str, delta_minor: int) -> None:
    db.execute("UPDATE users SET balance_minor = balance_minor + %s WHERE id = %s",
               (delta_minor, user_id))


def pay(db, user_id: str, amount_minor: int, ref: str, currency: str = "BRL",
        ledger: Ledger | None = None) -> None:
    """Debit the user's wallet, credit revenue. `ref` is the idempotency key (e.g. order id)."""
    ledger = ledger or _ledger(db)
    acct = wallet_account(user_id)
    if ledger.store.get_by_ref(ref) is None and ledger.balance(acct, currency) < amount_minor:
        raise LedgerError("insufficient funds")
    _, created = ledger.post(ref, [Posting(acct, DEBIT, amount_minor, currency),
                                   Posting(REVENUE, CREDIT, amount_minor, currency)])
    if created:
        _apply_cache(db, user_id, -amount_minor)


def top_up(db, user_id: str, amount_minor: int, ref: str, currency: str = "BRL",
           ledger: Ledger | None = None) -> None:
    ledger = ledger or _ledger(db)
    _, created = ledger.post(ref, [Posting(CASH, DEBIT, amount_minor, currency),
                                   Posting(wallet_account(user_id), CREDIT, amount_minor, currency)])
    if created:
        _apply_cache(db, user_id, amount_minor)


def reconcile(db, user_id: str, currency: str = "BRL", ledger: Ledger | None = None) -> int:
    """Returns cache - ledger (0 when healthy). Alert on non-zero."""
    ledger = ledger or _ledger(db)
    cached = db.execute("SELECT balance_minor FROM users WHERE id = %s", (user_id,)).fetchone()[0]
    return cached - ledger.balance(wallet_account(user_id), currency)


def rebuild_cache(db, user_id: str, currency: str = "BRL", ledger: Ledger | None = None) -> None:
    ledger = ledger or _ledger(db)
    db.execute("UPDATE users SET balance_minor = %s WHERE id = %s",
               (ledger.balance(wallet_account(user_id), currency), user_id))
