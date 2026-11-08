"""Nightly QuickBooks Online sync.

Posts one summary journal entry per tenant/day/mapped account pair. Idempotent:
re-running a day looks up the stored (our id -> their id, SyncToken, hash) pair and
no-ops or updates. Never overwrites an accountant's edit silently.

Collaborators (injected, so the job is testable against a recorded sandbox):

db:  query(sql, params) -> rows
     get_mapping(tenant, key) -> QBO account id or None   (explicit per-tenant table)
     get_pair(tenant, our_id) / save_pair(tenant, our_id, **fields)
     save_conflict(tenant, our_id, ours, theirs, policy)
     queue_unmapped(tenant, key, day, amount_cents)
     save_tokens(tenant, access, refresh, refresh_expires_at)  # one transaction
qbo: get_journal_entry(id), create_journal_entry(payload, requestid),
     update_journal_entry(payload, requestid), void_invoice(id, sync_token),
     first_open_date(after) -> date
Errors: ClosedPeriodError, StaleTokenError (QBO 5010), RateLimitError.
"""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

CONFLICT_POLICIES = ("ours", "theirs", "review")
DEFAULT_POLICY = "review"  # never overwrite silently


class ClosedPeriodError(Exception):
    pass


class StaleTokenError(Exception):
    pass


class RateLimitError(Exception):
    pass


def to_major(cents, decimals=2):
    """Minor units -> major units at the API boundary."""
    return float(Decimal(cents) / (Decimal(10) ** decimals))


def doc_number(day, kind):
    # our id in the DocNumber (QBO max 21 chars); unique per company
    return f"{kind}-{day:%Y%m%d}"


def _hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _request_id(tenant, our_id, digest):
    # unique per company, <= 36 chars so it is valid in batch too
    return hashlib.sha256(f"{tenant}:{our_id}:{digest}".encode()).hexdigest()[:36]


def build_entry(day, kind, cents, debit_id, credit_id, txn_date=None, memo=None):
    amount = to_major(cents)
    note = f"{kind} {day} ({doc_number(day, kind)})"
    if memo:
        note += f" - {memo}"
    return {
        "DocNumber": doc_number(day, kind),
        "TxnDate": str(txn_date or day),
        "PrivateNote": note,
        "Line": [
            {"Amount": amount, "DetailType": "JournalEntryLineDetail",
             "JournalEntryLineDetail": {"PostingType": "Credit", "AccountRef": {"value": credit_id}}},
            {"Amount": amount, "DetailType": "JournalEntryLineDetail",
             "JournalEntryLineDetail": {"PostingType": "Debit", "AccountRef": {"value": debit_id}}},
        ],
    }


def push_summary(db, qbo, tenant, day, kind, cents, debit_id, credit_id,
                 policy=DEFAULT_POLICY):
    """Create-or-update one summary entry. Returns a status string."""
    assert policy in CONFLICT_POLICIES
    our_id = doc_number(day, kind)
    payload = build_entry(day, kind, cents, debit_id, credit_id)
    digest = _hash(payload)
    pair = db.get_pair(tenant, our_id)

    if pair and pair["hash"] == digest:
        # unchanged on our side; still check the remote wasn't edited (flag only)
        remote = qbo.get_journal_entry(pair["their_id"])
        if remote["SyncToken"] != pair["sync_token"]:
            db.save_conflict(tenant, our_id, payload, remote, "review")
            return "conflict"
        return "noop"

    try:
        if pair is None:
            res = qbo.create_journal_entry(payload, requestid=_request_id(tenant, our_id, digest))
        else:
            remote = qbo.get_journal_entry(pair["their_id"])
            if remote["SyncToken"] != pair["sync_token"]:
                return _conflict(db, qbo, tenant, our_id, pair, payload, digest, remote, policy)
            res = _update(qbo, tenant, our_id, pair, payload, digest, remote["SyncToken"])
    except StaleTokenError:
        remote = qbo.get_journal_entry(pair["their_id"]) if pair else None
        db.save_conflict(tenant, our_id, payload, remote, "review")
        return "conflict"
    except ClosedPeriodError:
        # never retry: post in first open period, original date in the memo
        open_day = qbo.first_open_date(day)
        payload = build_entry(day, kind, cents, debit_id, credit_id, txn_date=open_day,
                              memo=f"original date {day}, period closed")
        digest = _hash(payload)
        res = qbo.create_journal_entry(payload, requestid=_request_id(tenant, our_id, digest))
        db.save_pair(tenant, our_id, their_id=res["Id"], sync_token=res["SyncToken"],
                     hash=digest, status="posted_in_open_period", error=f"closed period {day}")
        return "closed_period"

    db.save_pair(tenant, our_id, their_id=res["Id"], sync_token=res["SyncToken"],
                 hash=digest, status="synced", error=None)
    return "created" if pair is None else "updated"


def _update(qbo, tenant, our_id, pair, payload, digest, sync_token):
    body = dict(payload, Id=pair["their_id"], SyncToken=sync_token)
    return qbo.update_journal_entry(body, requestid=_request_id(tenant, our_id, digest))


def _conflict(db, qbo, tenant, our_id, pair, payload, digest, remote, policy):
    db.save_conflict(tenant, our_id, payload, remote, policy)  # both versions kept
    if policy == "ours":
        res = _update(qbo, tenant, our_id, pair, payload, digest, remote["SyncToken"])
        db.save_pair(tenant, our_id, their_id=res["Id"], sync_token=res["SyncToken"],
                     hash=digest, status="synced", error=None)
        return "updated_ours"
    if policy == "theirs":
        db.save_pair(tenant, our_id, their_id=pair["their_id"], sync_token=remote["SyncToken"],
                     hash=pair["hash"], status="synced_theirs", error=None)
        return "kept_theirs"
    return "conflict"  # review: leave remote untouched


def summarize(rows):
    """Integer cents per kind: sales (payments) and fees."""
    totals = {"sales": 0, "fees": 0}
    for r in rows:
        totals["sales"] += r.amount
        totals["fees"] += getattr(r, "fee", 0) or 0
    return totals


def nightly(db, qbo, tenant, today, policy=DEFAULT_POLICY):
    day = today - timedelta(days=1)
    rows = db.query(
        "SELECT * FROM payments WHERE tenant_id = %s AND created_at::date = %s",
        (tenant, day))
    totals = summarize(rows)
    results = {}
    pairs = {"sales": ("undeposited_funds", "sales"), "fees": ("bank_charges", "undeposited_funds")}
    for kind, (debit_key, credit_key) in pairs.items():
        cents = totals[kind]
        if cents == 0:
            continue
        debit, credit = db.get_mapping(tenant, debit_key), db.get_mapping(tenant, credit_key)
        if not debit or not credit:
            db.queue_unmapped(tenant, kind, day, cents)  # visible count for the customer
            results[kind] = "unmapped"
            continue
        try:
            results[kind] = push_summary(db, qbo, tenant, day, kind, cents, debit, credit, policy)
        except RateLimitError:
            results[kind] = "rate_limited"  # re-queued by the scheduler with backoff
    return results


def refresh_tokens(db, oauth, tenant, refresh_token):
    """Persist the rotated refresh token before anything else uses it."""
    t = oauth.refresh(refresh_token)
    db.save_tokens(tenant, t["access_token"], t["refresh_token"],
                   t["x_refresh_token_expires_in"])  # atomic; alert before expiry
    return t["access_token"]


def mirror_deleted_invoice(db, qbo, tenant, our_id):
    """A deleted invoice becomes a void in QBO, linked both ways. No hard delete."""
    pair = db.get_pair(tenant, our_id)
    if not pair:
        return "nothing_to_void"
    remote = qbo.void_invoice(pair["their_id"], pair["sync_token"])
    db.save_pair(tenant, our_id, their_id=pair["their_id"], sync_token=remote["SyncToken"],
                 hash=pair["hash"], status="voided", error=None, voided_of=our_id)
    return "voided"


def drift_report(ours, theirs, threshold_cents=0):
    """ours/theirs: {account_id: balance_cents}. Returns accounts that differ."""
    out = []
    for acct in sorted(set(ours) | set(theirs)):
        diff = ours.get(acct, 0) - theirs.get(acct, 0)
        if abs(diff) > threshold_cents:
            out.append({"account": acct, "ours": ours.get(acct, 0),
                        "theirs": theirs.get(acct, 0), "diff_cents": diff})
    return out
