"""Card sales."""

def record_sale(ledger, sale):
    ledger.post_cash_in(sale.amount_minor)
