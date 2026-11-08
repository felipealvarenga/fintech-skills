"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


def expected_totals(db, start, end):
    """Sum what our DB says should be in QBO per account, in integer cents.

    start/end are inclusive dates. Only sales are synced today; fees are not
    posted by nightly(), so any fee total in the P&L will show up as a mismatch.
    """
    rows = db.query(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM payments "
        "WHERE created_at::date BETWEEN %s AND %s",
        (start, end),
    )
    return {ACCOUNT_BY_NAME["sales"]: int(list(rows)[0].total)}


def reconcile(db, pnl, start, end):
    """Compare our balances with the customer's P&L report.

    pnl: dict of account name -> amount in dollars (str, int or Decimal) for
    the same period, e.g. parsed from the customer's report.
    Returns a list of discrepancies; empty means everything matches.
    """
    from decimal import Decimal

    ours = expected_totals(db, start, end)
    theirs = {k: round(Decimal(str(v)) * 100) for k, v in pnl.items()}
    diffs = []
    for account in sorted(set(ours) | set(theirs)):
        o, t = ours.get(account, 0), int(theirs.get(account, 0))
        if o != t:
            diffs.append({
                "account": account,
                "ours_cents": o,
                "pnl_cents": t,
                "difference_cents": o - t,
            })
    return diffs


def check_reconciliation(db, pnl, start, end):
    """Raise with a readable summary if balances differ from the P&L."""
    diffs = reconcile(db, pnl, start, end)
    if diffs:
        lines = [
            f"{d['account']}: ours {d['ours_cents']/100:.2f} vs P&L "
            f"{d['pnl_cents']/100:.2f} (diff {d['difference_cents']/100:+.2f})"
            for d in diffs
        ]
        raise AssertionError(f"Balances differ from P&L {start}..{end}:\n" + "\n".join(lines))


def nightly(db, qbo):
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"name": "Undeposited Funds"}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })
