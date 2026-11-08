"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


def nightly(db, qbo):
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"name": "Undeposited Funds"}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })


def _pnl_account_total(report, account_name):
    """Find an account's total in a QBO ProfitAndLoss report (nested Rows/ColData)."""
    def walk(rows):
        for row in rows.get("Row", []):
            cols = (row.get("ColData") or (row.get("Summary") or {}).get("ColData") or [])
            header = (row.get("Header") or {}).get("ColData") or []
            label = (cols or header)[0]["value"] if (cols or header) else None
            if label in (account_name, f"Total {account_name}") and cols:
                return cols[-1]["value"]
            found = walk(row.get("Rows") or {})
            if found is not None:
                return found
        return None

    return walk(report.get("Rows") or {})


def reconcile(db, qbo, start, end):
    """Compare our payment totals with QBO's Profit and Loss for [start, end].

    Returns a dict with cents-based totals and per-check mismatches; an empty
    `mismatches` list means the books agree. Read-only: posts nothing.
    """
    from decimal import Decimal

    row = db.query(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n FROM payments "
        "WHERE created_at::date BETWEEN %s AND %s", (start, end),
    )[0]
    ours_cents = int(row.total)

    report = qbo.get_report(
        "ProfitAndLoss", start_date=str(start), end_date=str(end), accounting_method="Accrual",
    )
    raw = _pnl_account_total(report, ACCOUNT_BY_NAME["sales"])
    qbo_cents = None if raw in (None, "") else int((Decimal(raw) * 100).to_integral_value())

    mismatches = []
    if qbo_cents is None:
        mismatches.append(f"'{ACCOUNT_BY_NAME['sales']}' not found in QBO P&L")
    elif qbo_cents != ours_cents:
        mismatches.append(
            f"Sales differ: ours={ours_cents / 100:.2f} qbo={qbo_cents / 100:.2f} "
            f"diff={(ours_cents - qbo_cents) / 100:+.2f}"
        )
    return {
        "start": str(start), "end": str(end), "payment_count": row.n,
        "ours_cents": ours_cents, "qbo_cents": qbo_cents, "mismatches": mismatches,
    }
