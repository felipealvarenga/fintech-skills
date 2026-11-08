"""Background job that sends approved refunds to the processor.

Duplicate-refund safety (see idempotent-payments rules 4, 5, 6):
- The refund is moved approved -> pending in the database *before* the processor
  call, using a guarded UPDATE so only one worker claims it.
- The processor call carries a deterministic idempotency key derived from the
  refund id, so a retry after a crash or timeout is deduplicated by the processor.
- A refund left 'pending' (crash, timeout, error) is an unknown outcome: the next
  run retries it with the SAME key; it is never marked failed or re-keyed.
"""


def idempotency_key(refund_id):
    return f"refund-{refund_id}"


def run(db, processor):
    # 'pending' rows are refunds a previous run may or may not have sent.
    rows = db.query("SELECT * FROM refunds WHERE status IN ('approved', 'pending')")
    for refund in rows:
        if refund.status == "approved":
            claimed = db.query(
                "UPDATE refunds SET status = 'pending' "
                "WHERE id = %s AND status = 'approved' RETURNING id",
                (refund.id,),
            )
            if not claimed:
                continue  # another worker claimed it

        try:
            processor.refund(
                refund.payment_id,
                refund.amount,
                idempotency_key=idempotency_key(refund.id),
            )
        except Exception:
            # Unknown outcome: leave 'pending' and retry later with the same key.
            continue

        db.execute(
            "UPDATE refunds SET status = 'sent' WHERE id = %s AND status = 'pending'",
            (refund.id,),
        )
