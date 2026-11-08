"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


def account_ref(qbo, name):
    """Look up the account by name in this company; ids differ per company."""
    rows = qbo.query(f"SELECT Id FROM Account WHERE Name = '{name}'")
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one QuickBooks account named {name!r}, found {len(rows)}")
    return {"value": rows[0]["Id"]}


def nightly(db, qbo):
    sales = account_ref(qbo, ACCOUNT_BY_NAME["sales"])
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": sales},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"name": "Undeposited Funds"}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })
