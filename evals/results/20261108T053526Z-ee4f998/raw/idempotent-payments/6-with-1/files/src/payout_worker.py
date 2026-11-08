"""Two workers poll this queue.

Status flow: queued -> sending -> sent | failed.
A job left in 'sending' (crash or timeout) has an unknown outcome; it is never
re-queued here. A reconciler must resolve it by querying the processor with the
job's idempotency key.
"""


class DefiniteFailure(Exception):
    """Processor confirmed the payout was rejected (e.g. 4xx validation/decline)."""


def process(db, client):
    # Atomic claim: the first worker flips queued -> sending; SKIP LOCKED makes
    # the other worker take a different row (or nothing) instead of the same one.
    job = db.query_one(
        """
        UPDATE payout_jobs SET status = 'sending'
        WHERE id = (
            SELECT id FROM payout_jobs
            WHERE status = 'queued'
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
        """
    )
    if job is None:
        return

    # Deterministic key from the job id: any retry presents the same key.
    key = f"payout-{job.id}"
    try:
        client.send_payout(job, idempotency_key=key)
    except DefiniteFailure:
        db.execute(
            "UPDATE payout_jobs SET status = 'failed' WHERE id = %s AND status = 'sending'",
            (job.id,),
        )
        raise
    # Any other exception (timeout, 5xx, crash) is an unknown outcome: leave the
    # job in 'sending' for the reconciler. Do not requeue.
    db.execute(
        "UPDATE payout_jobs SET status = 'sent' WHERE id = %s AND status = 'sending'",
        (job.id,),
    )
