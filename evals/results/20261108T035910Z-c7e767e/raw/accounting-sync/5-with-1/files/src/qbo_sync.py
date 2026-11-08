"""Nightly QuickBooks sync.

Posts one summary journal entry per day. Safe to re-run: the (our ref -> their id)
pair is looked up first, creates carry a requestid, and a closed-period refusal is
never retried: the entry is posted in the first open period with the original date
in the memo, and the case is surfaced to the customer.

Assumed interfaces (adapt to the real db/qbo wrappers):
  db.query(sql, *params) -> rows; db.get_sync_state(ref) / db.save_sync_state(...)
  db.get_account_map(tenant) -> {"sales": qbo_account_id, "undeposited": qbo_account_id}
  db.notify_customer(tenant, kind, detail)
  qbo.create_journal_entry(payload, requestid=...) -> {"Id", "SyncToken"}
  qbo.update_journal_entry(payload) -> {"Id", "SyncToken"}   (payload has Id + SyncToken)
  qbo.first_open_date() -> date   (from the company's books-closed date)
  qbo raises ClosedPeriodError for the period-closed refusal.
"""
import hashlib
import json
from datetime import date, timedelta


class ClosedPeriodError(Exception):
    pass


class UnmappedAccount(Exception):
    pass


def _lines(amount_major, accounts, memo):
    return [
        {"Amount": amount_major, "PostingType": "Credit", "Description": memo,
         "AccountRef": {"value": accounts["sales"]}},
        {"Amount": amount_major, "PostingType": "Debit", "Description": memo,
         "AccountRef": {"value": accounts["undeposited"]}},
    ]


def _push(db, qbo, tenant, ref, payload):
    """Create or update by pair lookup. Never creates without checking the pair."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    state = db.get_sync_state(ref)
    if state and state["hash"] == digest:
        return state  # no-op
    if state:
        res = qbo.update_journal_entry({**payload, "Id": state["remote_id"],
                                        "SyncToken": state["sync_token"]})
    else:
        res = qbo.create_journal_entry(payload, requestid=ref[:50])
    new = {"ref": ref, "remote_id": res["Id"], "sync_token": res["SyncToken"],
           "hash": digest, "status": "ok", "error": None}
    db.save_sync_state(new)
    return new


def nightly(db, qbo, tenant, day=None):
    day = day or (date.today() - timedelta(days=1))
    accounts = db.get_account_map(tenant)
    missing = [k for k in ("sales", "undeposited") if not accounts.get(k)]
    if missing:
        # Rule 1: nothing posts to a guessed account; queue for the customer.
        db.notify_customer(tenant, "unmapped_accounts", {"accounts": missing, "day": str(day)})
        return

    rows = db.query("SELECT COALESCE(SUM(amount), 0) AS total FROM payments "
                    "WHERE created_at::date = %s", day)
    total_minor = rows[0].total
    if not total_minor:
        return

    ref = f"{tenant}:sales:{day.isoformat()}"
    amount = total_minor / 100  # minor -> major at the boundary
    payload = {
        "DocNumber": ref[:21],
        "TxnDate": str(day),
        "PrivateNote": f"ref={ref}",
        "Line": _lines(amount, accounts, f"Sales {day}"),
    }
    try:
        _push(db, qbo, tenant, ref, payload)
    except ClosedPeriodError:
        # Rule 5: do not retry. Post in the first open period, note original date.
        open_day = qbo.first_open_date()
        memo = f"Sales for {day} (period closed; posted {open_day})"
        payload = {**payload, "TxnDate": str(open_day),
                   "PrivateNote": f"ref={ref}; original date {day}",
                   "Line": _lines(amount, accounts, memo)}
        _push(db, qbo, tenant, ref, payload)
        db.notify_customer(tenant, "closed_period_repost",
                           {"original_date": str(day), "posted_date": str(open_day),
                            "amount": amount})
