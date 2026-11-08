"""Processes the bank's return file for paid boletos."""

from datetime import date

# Brazilian defaults (multa 2% flat, juros de mora 1% per month pro rata).
# Override per call if the invoice/contract specifies other terms.
DEFAULT_FINE_RATE = 0.02
DEFAULT_MONTHLY_INTEREST_RATE = 0.01


def max_expected_minor(amount_minor, due_on, paid_on,
                       fine_rate=DEFAULT_FINE_RATE,
                       monthly_interest_rate=DEFAULT_MONTHLY_INTEREST_RATE):
    """Highest amount a legitimately late payment can reach (in minor units)."""
    days_late = (paid_on - due_on).days
    if days_late <= 0:
        return amount_minor
    fine = amount_minor * fine_rate
    interest = amount_minor * (monthly_interest_rate / 30) * days_late
    return amount_minor + int(round(fine + interest)) + 1  # +1 minor unit rounding slack


def is_acceptable_payment(invoice, paid_minor, paid_on, **terms):
    if paid_minor == invoice.amount_minor:
        return True
    # Late payments carry fine + interest, so paid >= face value.
    # Underpayments and payments above the computable max are NOT auto-matched.
    if paid_on > invoice.due_date:
        return invoice.amount_minor < paid_minor <= max_expected_minor(
            invoice.amount_minor, invoice.due_date, paid_on, **terms)
    return False


def apply_return(db, lines, **terms):
    """Returns the lines that were not matched, for manual review."""
    unmatched = []
    for line in lines:  # dict(nosso_numero=..., paid_minor=..., paid_on=date)
        invoice = db.query_one("SELECT * FROM invoices WHERE nosso_numero = %s", (line["nosso_numero"],))
        paid_on = line["paid_on"]
        if isinstance(paid_on, str):
            paid_on = date.fromisoformat(paid_on)
        if invoice and is_acceptable_payment(invoice, line["paid_minor"], paid_on, **terms):
            db.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", (invoice.id,))
        else:
            unmatched.append(line)
    return unmatched
