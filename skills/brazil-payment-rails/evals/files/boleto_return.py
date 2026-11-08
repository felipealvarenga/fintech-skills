"""Processes the bank's return file for paid boletos."""

def apply_return(db, lines):
    for line in lines:  # dict(nosso_numero=..., paid_minor=..., paid_on=...)
        invoice = db.query_one("SELECT * FROM invoices WHERE nosso_numero = %s", (line["nosso_numero"],))
        if invoice and invoice.amount_minor == line["paid_minor"]:
            db.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", (invoice.id,))
