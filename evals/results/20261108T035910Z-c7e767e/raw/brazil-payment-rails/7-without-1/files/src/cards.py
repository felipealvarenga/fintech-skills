"""Card sales."""

def record_sale(ledger, sale):
    ledger.post_cash_in(sale.amount_minor)


def split_installments(amount_minor, n):
    """Split an amount in minor units (centavos) into n parts that sum exactly.

    Any remainder centavos go to the first installments.
    """
    base, rem = divmod(amount_minor, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def record_installment_sale(ledger, amount_minor, installments):
    """Record a card sale paid in `installments` parts, one ledger entry each."""
    for part in split_installments(amount_minor, installments):
        ledger.post_cash_in(part)


def record_example_sale(ledger):
    """10x installment card sale of R$ 1.200,00 (120000 centavos -> 10 x R$ 120,00)."""
    record_installment_sale(ledger, 120_000, 10)
