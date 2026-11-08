"""Background job that sends approved refunds to the processor."""


def run(db, processor):
    for refund in db.query("SELECT * FROM refunds WHERE status = 'approved'"):
        # Pass a stable idempotency key (the refund id) so that if the worker
        # dies after the processor call but before the status update, the retry
        # on restart is deduplicated by the processor instead of refunding twice.
        processor.refund(
            refund.payment_id,
            refund.amount,
            idempotency_key=f"refund-{refund.id}",
        )
        db.execute(
            "UPDATE refunds SET status = 'sent' WHERE id = %s AND status = 'approved'",
            (refund.id,),
        )
