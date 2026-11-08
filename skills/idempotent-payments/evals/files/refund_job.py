"""Background job that sends approved refunds to the processor."""

def run(db, processor):
    for refund in db.query("SELECT * FROM refunds WHERE status = 'approved'"):
        processor.refund(refund.payment_id, refund.amount)
        db.execute("UPDATE refunds SET status = 'sent' WHERE id = %s", (refund.id,))
