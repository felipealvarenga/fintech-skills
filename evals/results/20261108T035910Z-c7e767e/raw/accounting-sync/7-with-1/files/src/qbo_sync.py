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


# --- Drift report: our balances vs. the customer's QuickBooks Profit and Loss ---
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class Drift:
    our_account: str
    qbo_account_id: str
    ours_cents: int
    theirs_cents: int

    @property
    def diff_cents(self):
        return self.ours_cents - self.theirs_cents


def _to_cents(amount):
    """QBO reports major units; convert at the edge, never with float math."""
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def drift_report(db, qbo, tenant_id, start, end, threshold_cents=0):
    """Compare our per-account totals for [start, end] with QBO's P&L.

    Returns {"drifts": [Drift], "unmapped": [our_account, ...]}.
    - Accounts come from the per-tenant mapping table (by QBO account id, not name).
    - Our activity with no mapping is reported as unmapped, never guessed.
    - Any |difference| > threshold_cents is returned; 0 flags even one cent.

    Assumed interfaces (adjust to the real schema/client):
      db.query(sql, params) -> rows with .our_account / .qbo_account_id / .cents
      qbo.profit_and_loss(start, end) -> {qbo_account_id: major-unit amount}
    """
    mapping = {
        r.our_account: r.qbo_account_id
        for r in db.query(
            "SELECT our_account, qbo_account_id FROM qbo_account_map WHERE tenant_id = %s",
            (tenant_id,),
        )
    }
    ours = {
        r.our_account: int(r.cents)
        for r in db.query(
            "SELECT account AS our_account, SUM(amount_cents) AS cents FROM ledger_entries "
            "WHERE tenant_id = %s AND posted_on BETWEEN %s AND %s GROUP BY account",
            (tenant_id, start, end),
        )
    }
    theirs = {k: _to_cents(v) for k, v in qbo.profit_and_loss(start, end).items()}

    unmapped = sorted(a for a in ours if a not in mapping)
    drifts = []
    for our_account, qbo_id in sorted(mapping.items()):
        d = Drift(our_account, qbo_id, ours.get(our_account, 0), theirs.get(qbo_id, 0))
        if abs(d.diff_cents) > threshold_cents:
            drifts.append(d)
    return {"drifts": drifts, "unmapped": unmapped}
