"""Push expense categorizations to Xero.

Conflict handling (accounting-sync rule 6): before writing, read the bank
transaction from Xero and compare it with what we last wrote. If the accountant
or customer changed it since, apply a named policy instead of overwriting.

Assumed schema additions (migration needed):
  expenses.xero_version         -- UpdatedDateUTC returned by Xero after our last push
  expenses.xero_account_code    -- account code we last wrote
  sync_conflicts(expense_id, xero_id, our_account_code, their_account_code,
                 their_updated_at, policy, status, created_at)
"""

OURS_WINS = "ours_wins"
THEIRS_WINS = "theirs_wins"
FLAG = "flag_for_review"

# Policy per object type. Default for categorizations: never overwrite silently.
CONFLICT_POLICY = {"expense_category": FLAG}


def _account_code(remote):
    items = remote.get("LineItems") or []
    codes = {i.get("AccountCode") for i in items}
    return codes.pop() if len(codes) == 1 else None


def _record_conflict(db, expense, remote, policy):
    db.execute(
        "INSERT INTO sync_conflicts (expense_id, xero_id, our_account_code, their_account_code, "
        "their_updated_at, policy, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, 'open', now())",
        (expense.id, expense.xero_id, expense.account_code, _account_code(remote),
         remote.get("UpdatedDateUTC"), policy),
    )


def _mark_synced(db, expense, version, account_code):
    db.execute(
        "UPDATE expenses SET synced = true, last_synced_at = now(), "
        "xero_version = %s, xero_account_code = %s WHERE id = %s",
        (version, account_code, expense.id),
    )


def push(db, xero, policy=None):
    policy = policy or CONFLICT_POLICY["expense_category"]
    for expense in db.query("SELECT * FROM expenses WHERE synced = false OR updated_at > last_synced_at"):
        remote = xero.get_bank_transaction(expense.xero_id)

        # Their edit = remote changed since the version we stored.
        edited_remotely = (
            expense.xero_version is not None
            and remote.get("UpdatedDateUTC") != expense.xero_version
        )
        remote_code = _account_code(remote)

        if edited_remotely and remote_code != expense.account_code:
            _record_conflict(db, expense, remote, policy)
            if policy == FLAG:
                continue  # leave Xero untouched; stays unsynced until resolved
            if policy == THEIRS_WINS:
                db.execute("UPDATE expenses SET account_code = %s WHERE id = %s",
                           (remote_code, expense.id))
                _mark_synced(db, expense, remote.get("UpdatedDateUTC"), remote_code)
                continue
            # OURS_WINS falls through to the write, with the conflict on record.

        if remote_code == expense.account_code:
            _mark_synced(db, expense, remote.get("UpdatedDateUTC"), expense.account_code)
            continue

        # Change only AccountCode; keep amounts, tax, descriptions as Xero has them.
        line_items = [{**i, "AccountCode": expense.account_code} for i in remote.get("LineItems", [])]
        updated = xero.update_bank_transaction(
            expense.xero_id, {"LineItems": line_items}
        )
        _mark_synced(db, expense, updated.get("UpdatedDateUTC"), expense.account_code)
