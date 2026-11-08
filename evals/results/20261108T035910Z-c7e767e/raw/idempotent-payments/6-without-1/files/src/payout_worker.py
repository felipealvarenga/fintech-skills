"""Two workers poll this queue."""

def process(db, client):
    # Atomically claim one job: the UPDATE only matches rows still 'queued',
    # and SKIP LOCKED keeps concurrent workers from blocking on / re-claiming
    # the same row. Only the worker that gets a row back may send it.
    job = db.query_one(
        """
        UPDATE payout_jobs SET status = 'processing'
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
    # If send_payout raises, the job stays 'processing' (not 'queued') on
    # purpose: the outcome is unknown, and auto-requeueing could double-pay.
    # Such jobs need reconciliation/manual review.
    client.send_payout(job)
    db.execute("UPDATE payout_jobs SET status = 'sent' WHERE id = %s", (job.id,))
