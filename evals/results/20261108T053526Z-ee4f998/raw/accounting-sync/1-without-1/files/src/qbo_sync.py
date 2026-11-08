"""Nightly QuickBooks sync.

Safe to re-run: each payment maps to one journal entry with a deterministic
DocNumber, and we skip payments that already have one in QBO. A failure on one
payment does not stop the others; failures are raised together at the end so
the job exits non-zero and the next run retries only what is missing.
"""

import logging
from decimal import Decimal

log = logging.getLogger(__name__)

ACCOUNT_BY_NAME = {"sales": "Sales", "fees": "Bank Charges"}
UNDEPOSITED_FUNDS = "Undeposited Funds"


class SyncError(Exception):
    def __init__(self, failures):
        super().__init__(f"{len(failures)} payment(s) failed to sync: {failures}")
        self.failures = failures


def _doc_number(payment):
    # QBO DocNumber max length is 21 chars.
    return f"PAY-{payment.id}"[:21]


def _dollars(cents):
    # Amounts are integer cents; avoid float rounding.
    return Decimal(int(cents)) / Decimal(100)


def _already_synced(qbo, doc_number):
    # ASSUMPTION: qbo wrapper exposes a lookup by DocNumber. Adjust to the real client.
    return qbo.find_journal_entry_by_doc_number(doc_number) is not None


def nightly(db, qbo):
    payments = db.query(
        "SELECT * FROM payments WHERE created_at::date = current_date - 1"
    )
    created, skipped, failures = 0, 0, []

    for payment in payments:
        doc_number = _doc_number(payment)
        try:
            if payment.amount is None or payment.amount <= 0:
                raise ValueError(f"unexpected amount {payment.amount!r}")
            if _already_synced(qbo, doc_number):
                skipped += 1
                continue
            amount = _dollars(payment.amount)
            qbo.create_journal_entry({
                "DocNumber": doc_number,
                "PrivateNote": f"payment {payment.id}",
                "Line": [
                    {"Amount": amount, "PostingType": "Credit",
                     "AccountRef": {"name": ACCOUNT_BY_NAME["sales"]}},
                    {"Amount": amount, "PostingType": "Debit",
                     "AccountRef": {"name": UNDEPOSITED_FUNDS}},
                ],
                "TxnDate": str(payment.created_at.date()),
            })
            created += 1
        except Exception as exc:  # keep going; report at the end
            log.exception("QBO sync failed for payment %s", payment.id)
            failures.append((payment.id, str(exc)))

    log.info("QBO sync: %d created, %d skipped, %d failed", created, skipped, len(failures))
    if failures:
        raise SyncError(failures)
