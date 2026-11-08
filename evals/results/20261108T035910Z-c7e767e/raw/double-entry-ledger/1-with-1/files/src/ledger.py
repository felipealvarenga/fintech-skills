"""Single write path for ledger postings. Amounts are integer minor units."""
from collections import defaultdict
from datetime import date

DEBIT, CREDIT = "debit", "credit"


class LedgerError(ValueError):
    pass


def validate_postings(postings):
    """postings: list of (account_id, side, amount_minor, currency)."""
    if len(postings) < 2:
        raise LedgerError("entry needs at least two postings")
    totals = defaultdict(int)
    for _acct, side, amount, currency in postings:
        if side not in (DEBIT, CREDIT):
            raise LedgerError(f"bad side {side!r}")
        if not isinstance(amount, int) or amount <= 0:
            raise LedgerError("posting amount must be a positive integer")
        totals[currency] += amount if side == DEBIT else -amount
    for currency, net in totals.items():
        if net != 0:
            raise LedgerError(f"unbalanced in {currency}: {net}")


def post(db, external_ref: str, effective_date: date, postings, reverses_id=None) -> int:
    """Post a balanced entry. Replaying external_ref returns the existing entry id."""
    validate_postings(postings)
    existing = db.execute("SELECT id FROM ledger_entries WHERE external_ref = %s", (external_ref,)).fetchone()
    if existing:
        return existing[0]
    closed = db.execute("SELECT closed_through FROM ledger_state").fetchone()[0]
    if closed is not None and effective_date <= closed:
        raise LedgerError(f"period closed through {closed}; post the adjustment in the open period")
    row = db.execute(
        "INSERT INTO ledger_entries (external_ref, effective_date, reverses_id) VALUES (%s, %s, %s) "
        "ON CONFLICT (external_ref) DO NOTHING RETURNING id",
        (external_ref, effective_date, reverses_id),
    ).fetchone()
    if row is None:  # lost a race with a concurrent identical post
        return db.execute("SELECT id FROM ledger_entries WHERE external_ref = %s", (external_ref,)).fetchone()[0]
    for acct, side, amount, currency in postings:
        db.execute(
            "INSERT INTO ledger_postings (entry_id, account_id, side, amount_minor, currency) "
            "VALUES (%s, %s, %s, %s, %s)",
            (row[0], acct, side, amount, currency),
        )
    return row[0]


def balance(db, account_id: int) -> int:
    """Derived balance in the account's normal-side direction."""
    return db.execute(
        "SELECT COALESCE(sum(CASE p.side WHEN a.normal_side THEN p.amount_minor ELSE -p.amount_minor END), 0) "
        "FROM ledger_postings p JOIN ledger_accounts a ON a.id = p.account_id WHERE a.id = %s",
        (account_id,),
    ).fetchone()[0]
