"""Processes the bank's return file for paid boletos."""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

# Brazilian defaults: 2% one-off late fee (multa) + 1% per month interest (juros),
# pro rata per day. Adjust to whatever is printed on the boleto / contracted with the bank.
LATE_FEE_RATE = Decimal("0.02")
DAILY_INTEREST_RATE = Decimal("0.01") / 30
TOLERANCE_MINOR = 1  # rounding differences between us and the bank


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def expected_amount_minor(amount_minor, due_date, paid_on):
    """Amount due on `paid_on`, including late fee and interest if past due."""
    days_late = (_as_date(paid_on) - _as_date(due_date)).days
    if days_late <= 0:
        return amount_minor
    base = Decimal(amount_minor)
    extra = base * LATE_FEE_RATE + base * DAILY_INTEREST_RATE * days_late
    return amount_minor + int(extra.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def apply_return(db, lines):
    """Marks matching invoices as paid. Returns the lines that could not be matched
    so they can be reviewed manually."""
    unmatched = []
    for line in lines:  # dict(nosso_numero=..., paid_minor=..., paid_on=...)
        invoice = db.query_one("SELECT * FROM invoices WHERE nosso_numero = %s", (line["nosso_numero"],))
        if not invoice:
            unmatched.append(line)
            continue
        expected = expected_amount_minor(invoice.amount_minor, invoice.due_date, line["paid_on"])
        if abs(line["paid_minor"] - expected) <= TOLERANCE_MINOR:
            db.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", (invoice.id,))
        else:
            unmatched.append(line)
    return unmatched
