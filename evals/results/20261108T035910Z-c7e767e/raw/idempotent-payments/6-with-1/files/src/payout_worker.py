"""Two workers poll this queue.

State machine: queued -> sending -> sent | failed.
A job is claimed with a single guarded UPDATE, so only one worker can move it
out of 'queued'. The row is persisted as 'sending' BEFORE the processor call.
"""


class RetryableLater(Exception):
    pass


def claim_next(db):
    # One statement: pick a queued row, skip rows other workers have locked,
    # and flip it to 'sending'. The loser never sees the same row.
    return db.query_one(
        """
        UPDATE payout_jobs SET status = 'sending'
        WHERE id = (
            SELECT id FROM payout_jobs
            WHERE status = 'queued'
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        AND status = 'queued'
        RETURNING *
        """
    )


def process(db, client):
    job = claim_next(db)
    if job is None:
        return

    # Deterministic key derived from the job id: any retry of this job,
    # by any worker, presents the same key to the processor.
    key = f"payout-{job.id}"

    try:
        client.send_payout(job, idempotency_key=key)
    except TimeoutError:
        # Unknown outcome: the payout may have gone out. Leave the job in
        # 'sending' for a reconciler to resolve by querying the processor
        # with `key`. Do NOT requeue it.
        raise
    # A confirmed failure from the processor (e.g. a declined/4xx error) should be
    # recorded as 'failed' by the caller once the client's error types are known.

    db.execute(
        "UPDATE payout_jobs SET status = 'sent' WHERE id = %s AND status = 'sending'",
        (job.id,),
    )
