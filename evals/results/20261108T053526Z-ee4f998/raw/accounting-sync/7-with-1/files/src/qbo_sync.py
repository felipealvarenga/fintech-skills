"""Nightly QuickBooks sync as it exists today."""

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}


def _to_cents(amount) -> int:
    """QBO reports major units; convert at the edge, never through float math."""
    from decimal import Decimal, ROUND_HALF_UP
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def drift_report(db, qbo, tenant_id, start, end, threshold_cents=0, open_task=None):
    """Compare our balance with QuickBooks' Profit and Loss, per mapped account.

    Read-only. Returns {"drifts": [...], "unmapped": [...]}; each drift is
    {our_account, qbo_account_id, ours_cents, theirs_cents, diff_cents, entries}.
    Any |diff| > threshold_cents is drift (default 0: a one-cent difference counts).

    Assumed interfaces (adapt to the real ones):
      db.query(sql, params) -> rows with attribute access
      qbo.profit_and_loss(start, end) -> {qbo_account_id: amount in major units}
      table account_mappings(tenant_id, our_account, qbo_account_id)
    """
    mappings = {
        m.our_account: m.qbo_account_id
        for m in db.query(
            "SELECT our_account, qbo_account_id FROM account_mappings WHERE tenant_id = %s",
            (tenant_id,),
        )
    }
    # Our side: payments are the only activity nightly() posts today (sales).
    ours = {"sales": 0}
    entries = []
    for p in db.query(
        "SELECT id, amount FROM payments WHERE tenant_id = %s "
        "AND created_at::date BETWEEN %s AND %s",
        (tenant_id, start, end),
    ):
        ours["sales"] += p.amount
        entries.append(p.id)

    theirs = qbo.profit_and_loss(start, end)

    drifts, unmapped = [], []
    for our_account, cents in ours.items():
        qbo_id = mappings.get(our_account)
        if qbo_id is None:
            # Never guess an account: surface it so the customer can map it.
            unmapped.append({"our_account": our_account, "ours_cents": cents})
            continue
        their_cents = _to_cents(theirs.get(qbo_id, 0))
        diff = cents - their_cents
        if abs(diff) > threshold_cents:
            drifts.append({
                "our_account": our_account,
                "qbo_account_id": qbo_id,
                "ours_cents": cents,
                "theirs_cents": their_cents,
                "diff_cents": diff,
                "entries": entries,  # compare against QBO entries carrying our ids
            })

    if (drifts or unmapped) and open_task:
        open_task(tenant_id, drifts, unmapped)
    return {"drifts": drifts, "unmapped": unmapped}


def nightly(db, qbo):
    for payment in db.query("SELECT * FROM payments WHERE created_at::date = current_date - 1"):
        qbo.create_journal_entry({
            "Line": [
                {"Amount": payment.amount / 100, "PostingType": "Credit", "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
                {"Amount": payment.amount / 100, "PostingType": "Debit", "AccountRef": {"name": "Undeposited Funds"}},
            ],
            "TxnDate": str(payment.created_at.date()),
        })
