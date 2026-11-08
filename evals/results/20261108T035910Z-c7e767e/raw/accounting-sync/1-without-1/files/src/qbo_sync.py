"""Nightly QuickBooks sync.

Safe to re-run: each payment is posted at most once, keyed by a deterministic
DocNumber, and one failing payment does not abort the rest of the batch.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal

log = logging.getLogger(__name__)

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}
UNDEPOSITED = "Undeposited Funds"


def _doc_number(payment) -> str:
    # QBO DocNumber max is 21 chars; the payment id is the idempotency key.
    return f"PAY-{payment.id}"[:21]


def _amount(cents) -> Decimal:
    # Integer cents -> exact decimal dollars (no float rounding).
    return (Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01"))


def _entry(payment) -> dict:
    amt = _amount(payment.amount)
    return {
        "DocNumber": _doc_number(payment),
        "PrivateNote": f"Auto-sync payment {payment.id}",
        "TxnDate": str(payment.created_at.date()),
        "Line": [
            {"Amount": amt, "PostingType": "Credit", "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
            {"Amount": amt, "PostingType": "Debit", "AccountRef": {"name": UNDEPOSITED}},
        ],
    }


def nightly(db, qbo, day: date | None = None) -> dict:
    """Sync payments created on `day` (default: yesterday). Returns a summary.

    Pass `day` explicitly to backfill or retry a specific date.
    """
    day = day or (date.today() - timedelta(days=1))
    payments = db.query(
        "SELECT * FROM payments WHERE created_at::date = %s "
        "AND qbo_synced_at IS NULL AND amount > 0 ORDER BY id",
        (day,),
    )
    done = failed = skipped = 0
    for payment in payments:
        doc = _doc_number(payment)
        try:
            # Guard against a crash between QBO create and our DB update.
            if qbo.find_journal_entry(doc_number=doc):
                skipped += 1
            else:
                qbo.create_journal_entry(_entry(payment))
                done += 1
            db.execute(
                "UPDATE payments SET qbo_synced_at = now() WHERE id = %s",
                (payment.id,),
            )
        except Exception:
            failed += 1
            log.exception("QBO sync failed for payment %s", payment.id)
    log.info("QBO sync %s: created=%d already_present=%d failed=%d", day, done, skipped, failed)
    if failed:
        raise RuntimeError(f"QBO sync {day}: {failed} payment(s) failed")
    return {"day": str(day), "created": done, "already_present": skipped, "failed": failed}
