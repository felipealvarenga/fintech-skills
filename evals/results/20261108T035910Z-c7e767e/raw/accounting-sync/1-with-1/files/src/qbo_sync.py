"""Nightly QuickBooks Online sync: one summary journal entry per tenant per day.

Safe to re-run: every push looks up the (tenant, day, kind) pair first, sends a
`requestid`, stores QBO's id + SyncToken, and never overwrites a remote edit.

Interfaces the caller provides
------------------------------
db.query(sql, params) -> list of rows (attribute access)
db.execute(sql, params)
qbo.create_journal_entry(payload, requestid) -> {"Id", "SyncToken"}
qbo.update_journal_entry(payload, requestid) -> {"Id", "SyncToken"}   # payload has Id+SyncToken
qbo.get_journal_entry(id) -> {"Id", "SyncToken", ...}
qbo.first_open_date(after) -> date
Errors: ClosedPeriodError, RateLimitError (raised by the qbo client wrapper).

Tables: account_mappings(tenant_id, key, qbo_account_id, set_by, set_at),
        unmapped_queue(tenant_id, day, key), sync_state(tenant_id, day, kind,
        qbo_id, sync_token, last_hash, status, error), sync_conflicts(tenant_id,
        day, kind, ours, theirs, created_at).
"""
import hashlib
import json
from datetime import date, timedelta

KIND = "sales_summary"
SALES_KEY = "sales"
CLEARING_KEY = "undeposited_funds"


class ClosedPeriodError(Exception):
    pass


class RateLimitError(Exception):
    pass


def doc_number(day):
    return f"SALES-{day.isoformat()}"  # our id, 16 chars (QBO limit 21)


def request_id(tenant_id, day, payload_hash):
    # Same content -> same id, so a crashed-and-retried create returns the original.
    return hashlib.sha256(f"{tenant_id}|{day}|{KIND}|{payload_hash}".encode()).hexdigest()[:36]


def to_major(cents):
    return f"{cents // 100}.{cents % 100:02d}" if cents >= 0 else f"-{abs(cents) // 100}.{abs(cents) % 100:02d}"


def build_payload(day, total_cents, accounts, txn_date=None, memo=None):
    amt = float(to_major(total_cents))
    note = f"Payments for {day.isoformat()}" + (f" {memo}" if memo else "")
    return {
        "DocNumber": doc_number(day),
        "TxnDate": (txn_date or day).isoformat(),
        "PrivateNote": note,
        "Line": [
            {"Amount": amt, "DetailType": "JournalEntryLineDetail", "JournalEntryLineDetail": {
                "PostingType": "Credit", "AccountRef": {"value": accounts[SALES_KEY]}}},
            {"Amount": amt, "DetailType": "JournalEntryLineDetail", "JournalEntryLineDetail": {
                "PostingType": "Debit", "AccountRef": {"value": accounts[CLEARING_KEY]}}},
        ],
    }


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def load_accounts(db, tenant_id):
    rows = db.query("SELECT key, qbo_account_id FROM account_mappings WHERE tenant_id = %s", (tenant_id,))
    return {r.key: r.qbo_account_id for r in rows}


def sync_day(db, qbo, tenant_id, day):
    """Returns one of: created, updated, unchanged, conflict, unmapped, deferred, skipped_empty."""
    accounts = load_accounts(db, tenant_id)
    missing = [k for k in (SALES_KEY, CLEARING_KEY) if k not in accounts]
    if missing:
        for k in missing:
            db.execute("INSERT INTO unmapped_queue (tenant_id, day, key) VALUES (%s, %s, %s) "
                       "ON CONFLICT DO NOTHING", (tenant_id, day, k))
        return "unmapped"  # visible count for the customer; nothing posts to a guess

    total = db.query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments "
        "WHERE tenant_id = %s AND status = 'settled' AND created_at::date = %s",
        (tenant_id, day))[0].total
    state = db.query("SELECT * FROM sync_state WHERE tenant_id = %s AND day = %s AND kind = %s",
                     (tenant_id, day, KIND))
    state = state[0] if state else None
    if state is None and total == 0:
        return "skipped_empty"

    payload = build_payload(day, total, accounts)
    h = payload_hash(payload)
    if state is not None and state.last_hash == h and state.status == "synced":
        return "unchanged"

    try:
        if state is None:
            result, action = _post(db, qbo, tenant_id, day, payload, h, create=True), "created"
        else:
            remote = qbo.get_journal_entry(state.qbo_id)
            if remote["SyncToken"] != state.sync_token:
                # Accountant edited it. Policy for journal entries: flag for review.
                db.execute("INSERT INTO sync_conflicts (tenant_id, day, kind, ours, theirs, created_at) "
                           "VALUES (%s, %s, %s, %s, %s, now())",
                           (tenant_id, day, KIND, json.dumps(payload), json.dumps(remote)))
                db.execute("UPDATE sync_state SET status = 'conflict' WHERE tenant_id = %s AND day = %s AND kind = %s",
                           (tenant_id, day, KIND))
                return "conflict"
            upd = dict(payload, Id=state.qbo_id, SyncToken=state.sync_token)
            result, action = _post(db, qbo, tenant_id, day, upd, h, create=False), "updated"
    except RateLimitError as e:
        _record(db, tenant_id, day, "retry", str(e))
        return "deferred"  # picked up by tomorrow's run or the retry queue

    _store(db, tenant_id, day, result, h)
    return action


def _post(db, qbo, tenant_id, day, payload, h, create):
    rid = request_id(tenant_id, day, h)
    call = qbo.create_journal_entry if create else qbo.update_journal_entry
    try:
        return call(payload, rid)
    except ClosedPeriodError:
        # Do not retry: post in the first open period, original date in the memo.
        open_day = qbo.first_open_date(day)
        moved = dict(payload, TxnDate=open_day.isoformat(),
                     PrivateNote=f"{payload['PrivateNote']} (original date {day.isoformat()}, period closed)")
        _record(db, tenant_id, day, "moved_to_open_period", f"posted {open_day}")
        return call(moved, request_id(tenant_id, day, h + "open"))


def _store(db, tenant_id, day, result, h):
    db.execute(
        "INSERT INTO sync_state (tenant_id, day, kind, qbo_id, sync_token, last_hash, status, error) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'synced', NULL) "
        "ON CONFLICT (tenant_id, day, kind) DO UPDATE SET qbo_id = EXCLUDED.qbo_id, "
        "sync_token = EXCLUDED.sync_token, last_hash = EXCLUDED.last_hash, status = 'synced', error = NULL",
        (tenant_id, day, KIND, result["Id"], result["SyncToken"], h))


def _record(db, tenant_id, day, status, error):
    db.execute("UPDATE sync_state SET status = %s, error = %s WHERE tenant_id = %s AND day = %s AND kind = %s",
               (status, error, tenant_id, day, KIND))


def nightly(db, qbo, today=None, lookback_days=3):
    """Re-sync yesterday plus a short lookback so late payments and failed days heal."""
    today = today or date.today()
    results = {}
    tenants = db.query("SELECT id FROM tenants WHERE qbo_connected")
    for t in tenants:
        for n in range(1, lookback_days + 1):
            day = today - timedelta(days=n)
            try:
                results[(t.id, day)] = sync_day(db, qbo, t.id, day)
            except Exception as e:  # one bad tenant/day must not stop the run
                results[(t.id, day)] = f"error: {e}"
    return results
