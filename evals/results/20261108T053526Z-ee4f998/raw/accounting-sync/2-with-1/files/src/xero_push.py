"""Push expense categorizations to Xero without overwriting the customer's edits.

Before each write we read the bank transaction from Xero and compare it with what we
last wrote (account codes and UpdatedDateUTC, stored on the expense row). If they differ,
someone edited it in Xero and the conflict policy decides what happens. Every conflict is
stored in sync_conflicts with both versions. Nothing is overwritten silently.

Expected columns on expenses (add by migration):
  xero_updated_utc          UpdatedDateUTC returned by Xero after our last write/read
  last_pushed_account_code  the account code we last wrote
  sync_status               'pending' | 'synced' | 'conflict'
Expected table sync_conflicts(expense_id, xero_id, ours, theirs, policy, created_at).
"""
import json

OURS = "ours"      # our categorization wins; Xero is overwritten, conflict is recorded
THEIRS = "theirs"  # Xero's categorization wins; our ledger is updated, nothing is pushed
FLAG = "flag"      # nothing is written on either side; a human resolves it

POLICIES = {OURS, THEIRS, FLAG}
# Per object type. Recategorization by an accountant is the case that matters: flag by default.
CONFLICT_POLICY = {"expense_category": FLAG}


def _codes(txn):
    return [li.get("AccountCode") for li in txn.get("LineItems", [])]


def _record_conflict(db, expense, remote, policy):
    db.execute(
        "INSERT INTO sync_conflicts (expense_id, xero_id, ours, theirs, policy, created_at) "
        "VALUES (%s, %s, %s, %s, %s, now())",
        (
            expense.id,
            expense.xero_id,
            json.dumps({"AccountCode": expense.account_code}),
            json.dumps({"AccountCodes": _codes(remote), "UpdatedDateUTC": remote.get("UpdatedDateUTC")}),
            policy,
        ),
    )


def _write(db, xero, expense, remote):
    lines = [dict(li, AccountCode=expense.account_code) for li in remote.get("LineItems", [])]
    updated = xero.update_bank_transaction(expense.xero_id, {"LineItems": lines})
    db.execute(
        "UPDATE expenses SET synced = true, sync_status = 'synced', last_synced_at = now(), "
        "last_pushed_account_code = %s, xero_updated_utc = %s WHERE id = %s",
        (expense.account_code, (updated or {}).get("UpdatedDateUTC"), expense.id),
    )


def _edited_remotely(expense, remote):
    if expense.xero_updated_utc is None:
        return False  # never pushed: nothing of ours to protect
    changed_time = remote.get("UpdatedDateUTC") != expense.xero_updated_utc
    changed_codes = any(c != expense.last_pushed_account_code for c in _codes(remote))
    return changed_time and changed_codes


def push(db, xero, policy=None):
    policy = policy or CONFLICT_POLICY["expense_category"]
    if policy not in POLICIES:
        raise ValueError(f"unknown conflict policy: {policy}")

    rows = db.query(
        "SELECT * FROM expenses "
        "WHERE sync_status <> 'conflict' AND (synced = false OR updated_at > last_synced_at)"
    )
    for expense in rows:
        remote = xero.get_bank_transaction(expense.xero_id)

        if not _edited_remotely(expense, remote):
            _write(db, xero, expense, remote)
            continue

        _record_conflict(db, expense, remote, policy)
        if policy == OURS:
            _write(db, xero, expense, remote)
        elif policy == THEIRS:
            codes = _codes(remote)
            db.execute(
                "UPDATE expenses SET account_code = %s, synced = true, sync_status = 'synced', "
                "last_synced_at = now(), last_pushed_account_code = %s, xero_updated_utc = %s "
                "WHERE id = %s",
                (codes[0] if codes else None, codes[0] if codes else None,
                 remote.get("UpdatedDateUTC"), expense.id),
            )
        else:  # FLAG
            db.execute("UPDATE expenses SET sync_status = 'conflict' WHERE id = %s", (expense.id,))
