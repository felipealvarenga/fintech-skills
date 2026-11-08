"""Nightly QuickBooks sync: one summary journal entry per day, idempotent, closed-period safe.

Assumed interfaces (adapt to the real clients):
  db.query(sql, params)            -> rows
  state                            -> sync-state store: get(our_id) / save(our_id, **fields)
  qbo.create_journal_entry(payload, request_id=...) -> {"Id": ..., "SyncToken": ...}
  qbo.first_open_date(after)       -> date of the first open period on/after `after`
  qbo.ClosedPeriodError            -> raised when QBO refuses a closed-period posting
"""
import hashlib
from datetime import date, timedelta


class UnmappedAccount(Exception):
    pass


def _account_ref(mapping, key):
    """Mapping is per tenant: our key -> QBO account id. Never post to a guessed name."""
    try:
        return {"value": mapping[key]}
    except KeyError:
        raise UnmappedAccount(key)


def build_entry(tenant_id, day, total_minor, mapping, txn_date=None, note=None):
    amount = round(total_minor / 100, 2)  # minor -> major units at the edge
    our_id = f"{tenant_id}:sales:{day.isoformat()}"
    memo = f"ref {our_id}"
    if note:
        memo += f" | {note}"
    return our_id, {
        "DocNumber": hashlib.sha1(our_id.encode()).hexdigest()[:21],
        "PrivateNote": memo,
        "TxnDate": (txn_date or day).isoformat(),
        "Line": [
            {"Amount": amount, "DetailType": "JournalEntryLineDetail",
             "JournalEntryLineDetail": {"PostingType": "Credit", "AccountRef": _account_ref(mapping, "sales")}},
            {"Amount": amount, "DetailType": "JournalEntryLineDetail",
             "JournalEntryLineDetail": {"PostingType": "Debit", "AccountRef": _account_ref(mapping, "undeposited")}},
        ],
    }


def push_day(qbo, state, tenant_id, day, total_minor, mapping):
    """Create-or-no-op for one day. Closed periods are never retried."""
    our_id, payload = build_entry(tenant_id, day, total_minor, mapping)
    existing = state.get(our_id)
    payload_hash = hashlib.sha256(repr(payload).encode()).hexdigest()
    if existing and existing.get("status") in ("posted", "posted_open_period") \
            and existing["hash"] == payload_hash:
        return existing  # already pushed, unchanged
    if existing and existing.get("qbo_id"):
        # Amount changed after posting: needs a sparse update with SyncToken and
        # conflict detection (rules 3 and 6). Flag instead of creating a duplicate.
        state.save(our_id, status="needs_update", error="changed after post")
        return state.get(our_id)

    try:
        res = qbo.create_journal_entry(payload, request_id=our_id[:50])
        status = "posted"
    except qbo.ClosedPeriodError:
        open_day = qbo.first_open_date(day)
        _, payload = build_entry(
            tenant_id, day, total_minor, mapping, txn_date=open_day,
            note=f"original date {day.isoformat()}, period closed")
        res = qbo.create_journal_entry(payload, request_id=(our_id + ":open")[:50])
        status = "posted_open_period"  # surfaced to the customer in the product

    state.save(our_id, qbo_id=res["Id"], sync_token=res.get("SyncToken"),
               hash=payload_hash, status=status, error=None)
    return state.get(our_id)


def nightly(db, qbo, state, tenant_id, mapping):
    day = date.today() - timedelta(days=1)
    rows = db.query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE created_at::date = %s",
        (day,))
    total = rows[0].total
    if not total:
        return None
    try:
        return push_day(qbo, state, tenant_id, day, total, mapping)
    except UnmappedAccount as e:
        # Queue for the customer to map; do not post and do not retry blindly.
        state.save(f"{tenant_id}:sales:{day.isoformat()}", status="unmapped", error=str(e))
        return None
