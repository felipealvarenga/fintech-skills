"""Push expense categorizations to Xero."""

def push(db, xero):
    for expense in db.query("SELECT * FROM expenses WHERE synced = false OR updated_at > last_synced_at"):
        xero.update_bank_transaction(expense.xero_id, {"LineItems": [{"AccountCode": expense.account_code}]})
        db.execute("UPDATE expenses SET synced = true, last_synced_at = now() WHERE id = %s", (expense.id,))
