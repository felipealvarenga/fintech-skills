"""Background job that sends approved refunds to the processor.

Safe against worker restarts and concurrent workers:
  * the row is claimed (approved -> pending) with a guarded UPDATE before the call,
  * the processor idempotency key is derived from the refund id, so a retry
    after a crash or timeout presents the same key,
  * a timeout/unknown outcome leaves the row 'pending' for the reconciler;
    it is never re-sent under a new key.

Assumes: db.execute(...) returns the affected row count, and
processor.refund(payment_id, amount, idempotency_key=...) plus
processor.find_refund(reference) exist. Adjust to the real interfaces.
"""


class ProcessorDeclined(Exception):
    """Confirmed failure from the processor (not a timeout)."""


def idempotency_key(refund_id):
    return f"refund-{refund_id}"


def _claim(db, refund_id):
    # First writer wins: only one worker can move approved -> pending.
    return db.execute(
        "UPDATE refunds SET status = 'pending' WHERE id = %s AND status = 'approved'",
        (refund_id,),
    ) == 1


def _send(db, processor, refund):
    try:
        result = processor.refund(
            refund.payment_id, refund.amount,
            idempotency_key=idempotency_key(refund.id),
        )
    except ProcessorDeclined:
        db.execute(
            "UPDATE refunds SET status = 'failed' WHERE id = %s AND status = 'pending'",
            (refund.id,),
        )
        return
    except Exception:
        # Timeout / network error = unknown outcome. Stay 'pending'; reconciler resolves.
        return
    db.execute(
        "UPDATE refunds SET status = 'sent', processor_ref = %s "
        "WHERE id = %s AND status = 'pending'",
        (getattr(result, "id", None), refund.id),
    )


def run(db, processor):
    for refund in db.query("SELECT * FROM refunds WHERE status = 'approved'"):
        if _claim(db, refund.id):
            _send(db, processor, refund)


def reconcile(db, processor):
    """Resolve refunds left 'pending' by a crash or timeout.

    Re-sends with the SAME idempotency key, so the processor returns the original
    result instead of refunding again. Alert on pending rows older than the SLA.
    """
    for refund in db.query("SELECT * FROM refunds WHERE status = 'pending'"):
        _send(db, processor, refund)
