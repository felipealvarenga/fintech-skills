"""Processes the bank's return file for paid boletos.

A boleto paid after `vencimento` is settled for amount + multa + juros de mora,
as registered with the bank, so the paid amount legitimately differs from the
invoice amount. Expected amounts are computed from the registration fields on
the invoice (assumed columns, adjust to the real schema):

    due_date            date, already moved to a business day at issuance
    multa_bps           one-time fine, basis points of amount (200 = 2%)
    juros_monthly_bps   daily interest registered as monthly rate, bps (100 = 1%/month),
                        accrued simple, per calendar day: rate / 30

`is_business_day` is optional; when given, a payment on a non-business day is
treated as on time if the due date falls on that run of non-business days
(grace until the next business day).
"""
from datetime import date, timedelta


def _round_div(num, den):
    return (2 * num + den) // (2 * den)  # half-up, integers only


def normalize_nosso_numero(value):
    """Return files zero-pad differently from our records; compare without leading zeros."""
    return str(value).strip().lstrip("0") or "0"


def expected_amount_minor(invoice, paid_on, is_business_day=None):
    due = invoice.due_date
    if is_business_day is not None:
        while not is_business_day(due):
            due += timedelta(days=1)
    days_late = (paid_on - due).days
    base = invoice.amount_minor
    if days_late <= 0:
        return base
    multa = _round_div(base * (invoice.multa_bps or 0), 10_000)
    juros = _round_div(base * (invoice.juros_monthly_bps or 0) * days_late, 10_000 * 30)
    return base + multa + juros


def apply_return(db, lines, is_business_day=None):
    """Marks matching invoices paid. Returns lines needing manual review."""
    review = []
    key_of = normalize_nosso_numero
    for line in lines:  # dict(nosso_numero=..., paid_minor=..., paid_on=date)
        matches = db.query_all(
            "SELECT * FROM invoices WHERE TRIM(LEADING '0' FROM nosso_numero) = %s",
            (key_of(line["nosso_numero"]),),
        )
        invoice = matches[0] if len(matches) == 1 else None
        if invoice is None:
            review.append((line, "unknown nosso_numero"))
            continue
        if invoice.status == "paid":
            continue  # duplicate return line, already processed
        expected = expected_amount_minor(invoice, line["paid_on"], is_business_day)
        if line["paid_minor"] == expected:
            db.execute("UPDATE invoices SET status = 'paid' WHERE id = %s", (invoice.id,))
        else:
            # Under/over payment is not silently credited: left pending for review.
            review.append((line, f"paid {line['paid_minor']} != expected {expected}"))
    return review
