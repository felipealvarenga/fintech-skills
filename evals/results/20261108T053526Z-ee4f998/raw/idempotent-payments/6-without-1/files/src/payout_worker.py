"""Two workers poll this queue."""

CLAIM_SQL = """
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


def process(db, client):
    # Atomically claim a job: only one worker can move it queued -> processing.
    job = db.query_one(CLAIM_SQL)
    if job is None:
        return
    try:
        client.send_payout(job)
    except Exception:
        # Outcome of the send is unknown, so don't requeue automatically
        # (that could cause a duplicate payout). Flag for manual review.
        db.execute("UPDATE payout_jobs SET status = 'failed' WHERE id = %s", (job.id,))
        raise
    db.execute("UPDATE payout_jobs SET status = 'sent' WHERE id = %s", (job.id,))
