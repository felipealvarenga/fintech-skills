"""Card sales."""
from datetime import timedelta


def installment_schedule(amount_minor, installments, sale_date):
    """Split amount_minor (integer centavos) into monthly receivables (D+30 each).

    Rounding remainder goes to the first installments so the rows sum exactly.
    """
    base, remainder = divmod(amount_minor, installments)
    return [
        (sale_date + timedelta(days=30 * n), base + (1 if n <= remainder else 0))
        for n in range(1, installments + 1)
    ]


def record_sale(ledger, sale):
    """Record a card sale as a receivable schedule, not as cash.

    Cash arrives per installment on settlement. MDR is not applied here;
    pass the net amount in sale.amount_minor once the acquirer's rate is known.
    """
    installments = getattr(sale, "installments", 1)
    for due_date, amount in installment_schedule(
        sale.amount_minor, installments, sale.date
    ):
        ledger.post_receivable(amount, due_date)
