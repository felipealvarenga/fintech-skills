"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


class ClosedPeriodError(Exception):
    """Raised by the qbo client when QuickBooks refuses a posting in a closed period."""


def void_invoice(db, qbo, invoice_id):
    """Mirror an invoice deletion in QuickBooks as a void, never a hard delete.

    Looks up the (our id, their id, SyncToken) pair in qbo_sync_state, voids with
    an idempotent request id, and records the void against the original.
    Returns the status: "voided", "not_synced" or "already_voided".
    """
    pair = db.query_one(
        "SELECT qbo_id, sync_token, status FROM qbo_sync_state "
        "WHERE object_type = 'invoice' AND our_id = %s",
        invoice_id,
    )
    if pair is None:
        # Never pushed to QuickBooks: nothing to void.
        return "not_synced"
    if pair.status == "voided":
        return "already_voided"

    try:
        result = qbo.void_invoice(
            qbo_id=pair.qbo_id,
            sync_token=pair.sync_token,
            request_id=f"void-invoice-{invoice_id}",  # <= 50 chars, repeat returns original
        )
    except ClosedPeriodError:
        # Rule 5: do not retry; queue for the customer instead of failing silently.
        db.execute(
            "UPDATE qbo_sync_state SET status = 'needs_review', "
            "error = 'closed period: void refused' "
            "WHERE object_type = 'invoice' AND our_id = %s",
            invoice_id,
        )
        return "needs_review"
    # A stale SyncToken (error 5010) propagates: the accountant changed the invoice,
    # so the caller must record a conflict instead of overwriting.

    db.execute(
        "UPDATE qbo_sync_state SET status = 'voided', sync_token = %s, "
        "voided_at = now(), error = NULL "
        "WHERE object_type = 'invoice' AND our_id = %s",
        result["SyncToken"],
        invoice_id,
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
