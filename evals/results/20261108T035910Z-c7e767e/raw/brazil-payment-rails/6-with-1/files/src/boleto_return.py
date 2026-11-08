"""Processes the bank's return file for paid boletos."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def _norm(nosso_numero):
    # Banks zero-pad differently between remessa and retorno.
    return str(nosso_numero).strip().lstrip("0")


def expected_minor(invoice, paid_on, next_business_day=lambda d: d):
    """Amount due on `paid_on`, in minor units (centavos).

    On or before the due date (moved to the next business day) it is the face
    amount. After it, add the one-time multa and pro-rata daily juros de mora
    exactly as registered with the bank.
    """
    due = next_business_day(invoice.due_date)
    days_late = (paid_on - due).days
    if days_late <= 0:
        return invoice.amount_minor
    base = Decimal(invoice.amount_minor)
    multa = base * Decimal(invoice.multa_pct) / 100
    # juros_mora_pct_month is a monthly rate, charged pro rata per day (30-day month).
    juros = base * Decimal(invoice.juros_mora_pct_month) / 100 / 30 * days_late
    return int((base + multa + juros).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def apply_return(db, lines, next_business_day=lambda d: d):
    """Mark invoices paid from the return file.

    Returns the lines left unmatched (unknown nosso número, amount below what is
    owed, or different from the registered multa/juros) for manual review.
    """
    unmatched = []
    for line in lines:  # dict(nosso_numero=..., paid_minor=..., paid_on=date)
        invoice = db.query_one(
            "SELECT * FROM invoices WHERE TRIM(LEADING '0' FROM nosso_numero) = %s",
            (_norm(line["nosso_numero"]),),
        )
        if not invoice or invoice.status == "paid":
            if not invoice:
                unmatched.append(line)
            continue  # already-paid: return files can be replayed
        paid_on = line["paid_on"]
        if isinstance(paid_on, str):
            paid_on = date.fromisoformat(paid_on)
        # 1 centavo tolerance for the bank's rounding of juros.
        if abs(line["paid_minor"] - expected_minor(invoice, paid_on, next_business_day)) <= 1:
            db.execute(
                "UPDATE invoices SET status = 'paid', paid_minor = %s, paid_on = %s WHERE id = %s",
                (line["paid_minor"], paid_on, invoice.id),
            )
        else:
            unmatched.append(line)
    return unmatched
