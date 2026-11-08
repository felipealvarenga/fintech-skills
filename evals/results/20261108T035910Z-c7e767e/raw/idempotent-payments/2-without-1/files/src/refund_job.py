"""Background job that sends approved refunds to the processor.

Double-refund protection:
1. Each refund is atomically claimed (approved -> sending) before calling the
   processor, so concurrent/restarted workers never pick up the same row.
2. The refund id is sent as an idempotency key, so if the worker dies after the
   processor call but before we mark 'sent', a retry is deduplicated by the
   processor instead of paying out twice.
3. Rows stuck in 'sending' (crash mid-flight) are NOT automatically re-sent;
   they are retried only with the same idempotency key via `recover_stuck`.
"""


def run(db, processor):
    for refund in db.query("SELECT * FROM refunds WHERE status = 'approved'"):
        # Atomic claim: only one worker can flip approved -> sending.
        claimed = db.execute(
            "UPDATE refunds SET status = 'sending' WHERE id = %s AND status = 'approved'",
            (refund.id,),
        )
        if not claimed:  # rowcount 0 -> someone else has it
            continue
        _send(db, processor, refund)


def recover_stuck(db, processor):
    """Retry refunds left in 'sending' after a crash. Safe because the
    processor deduplicates on the idempotency key."""
    for refund in db.query("SELECT * FROM refunds WHERE status = 'sending'"):
        _send(db, processor, refund)


def _send(db, processor, refund):
    try:
        processor.refund(
            refund.payment_id,
            refund.amount,
            idempotency_key=f"refund-{refund.id}",
        )
    except Exception:
        # Outcome unknown; leave as 'sending' for recover_stuck rather than
        # returning to 'approved', which could cause a duplicate.
        raise
    db.execute("UPDATE refunds SET status = 'sent' WHERE id = %s", (refund.id,))
