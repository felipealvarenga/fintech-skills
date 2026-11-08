"""Card sales."""

def record_sale(ledger, sale):
    ledger.post_cash_in(sale.amount_minor)


def split_installments(amount_minor, n):
    """Split an amount in minor units into n parts; remainder goes to the first parts."""
    base, rem = divmod(amount_minor, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def record_installment_sale(ledger, amount_minor, installments):
    """Record an installment card sale as one cash-in entry per installment."""
    parts = split_installments(amount_minor, installments)
    for part in parts:
        ledger.post_cash_in(part)
    return parts


# 10x card sale of R$ 1.200,00 -> 10 installments of R$ 120,00
def record_sale_10x_1200(ledger):
    return record_installment_sale(ledger, 120000, 10)
