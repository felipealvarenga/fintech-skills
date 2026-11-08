"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


def resolve_account_id(qbo, name):
    """Look up this company's account id by name. Ids differ per company."""
    rows = qbo.query(f"SELECT Id FROM Account WHERE Name = '{name}'")
    if len(rows) != 1:
        # Missing or ambiguous: never guess. Surface it so the customer can fix the chart.
        raise LookupError(f"QuickBooks account {name!r} not found uniquely ({len(rows)} matches)")
    return rows[0]["Id"]


def nightly(db, qbo):
    sales_id = resolve_account_id(qbo, ACCOUNT_BY_NAME["sales"])
    undeposited_id = resolve_account_id(qbo, "Undeposited Funds")
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": {"value": sales_id}},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"value": undeposited_id}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })
