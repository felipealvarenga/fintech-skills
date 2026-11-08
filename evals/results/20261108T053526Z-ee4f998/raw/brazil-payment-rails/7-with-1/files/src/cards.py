"""Card sales."""
from datetime import timedelta


def build_receivable_schedule(amount_minor, installments, sale_date):
    """Split amount_minor (integer centavos) into one receivable per installment.

    The merchant receives one installment per month (D+30 each), so the sale
    is a receivable schedule, not cash. Remainder centavos go to the first
    installments so the rows always sum exactly to amount_minor.
    """
    if installments < 1:
        raise ValueError("installments must be >= 1")
    base, remainder = divmod(amount_minor, installments)
    return [
        {
            "number": n,
            "amount_minor": base + (1 if n <= remainder else 0),
            "due_date": sale_date + timedelta(days=30 * n),
        }
        for n in range(1, installments + 1)
    ]


def record_sale(ledger, sale):
    """Record a card sale as a receivable schedule (one row per installment).

    Cash is posted later, per installment, when the acquirer settles it.
    """
    installments = getattr(sale, "installments", 1)
    schedule = build_receivable_schedule(
        sale.amount_minor, installments, sale.date
    )
    for row in schedule:
        ledger.post_receivable(
            amount_minor=row["amount_minor"],
            due_date=row["due_date"],
            installment=row["number"],
            of=installments,
        )
    return schedule
