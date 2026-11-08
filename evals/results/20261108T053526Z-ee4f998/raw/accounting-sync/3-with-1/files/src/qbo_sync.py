"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


class StaleSyncToken(Exception):
    """QBO error 5010: the SyncToken we hold is out of date."""


class ClosedPeriod(Exception):
    """QBO refused the change because the period is closed."""


def void_invoice(db, qbo, invoice_id):
    """Mirror an invoice deletion in QuickBooks as a void (never a hard delete).

    Expects a sync-state table `qbo_invoice_sync(our_id, qbo_id, sync_token,
    status, error, voided_at)` filled when the invoice was pushed.
    Returns the resulting status.
    """
    rows = db.query("SELECT * FROM qbo_invoice_sync WHERE our_id = %s", (invoice_id,))
    if not rows:
        return "not_synced"  # never reached QuickBooks, nothing to void
    pair = rows[0]
    if pair.status == "voided":
        return "voided"  # idempotent: already mirrored

    try:
        # Read the current version first so an accountant's edit is not clobbered.
        current = qbo.get_invoice(pair.qbo_id)
        if current["SyncToken"] != pair.sync_token:
            raise StaleSyncToken()
        result = qbo.void_invoice(
            pair.qbo_id,
            current["SyncToken"],
            requestid=f"void-inv-{invoice_id}"[:50],
        )
    except StaleSyncToken:
        # They changed it; flag for review instead of overwriting.
        db.execute(
            "UPDATE qbo_invoice_sync SET status = 'conflict', error = %s WHERE our_id = %s",
            ("stale SyncToken on void", invoice_id),
        )
        return "conflict"
    except ClosedPeriod:
        # Do not retry; surface to the customer for a reversing entry in the open period.
        db.execute(
            "UPDATE qbo_invoice_sync SET status = 'needs_review', error = %s WHERE our_id = %s",
            ("closed period", invoice_id),
        )
        return "needs_review"

    db.execute(
        "UPDATE qbo_invoice_sync SET status = 'voided', sync_token = %s, voided_at = now(), error = NULL "
        "WHERE our_id = %s",
        (result["SyncToken"], invoice_id),
    )
    return "voided"


def nightly(db, qbo):
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"name": "Undeposited Funds"}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })
