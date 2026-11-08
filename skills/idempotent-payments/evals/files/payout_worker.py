"""Two workers poll this queue."""

def process(db, client):
    job = db.query_one("SELECT * FROM payout_jobs WHERE status = 'queued' LIMIT 1")
    if job is None:
        return
    client.send_payout(job)
    db.execute("UPDATE payout_jobs SET status = 'sent' WHERE id = %s", (job.id,))
