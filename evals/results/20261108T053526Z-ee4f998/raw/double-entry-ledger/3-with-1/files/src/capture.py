"""Card capture posting: gross, processor fee, our cut; remainder owed to merchant."""
from datetime import date

from ledger import CREDIT, DEBIT, Entry, Ledger, LedgerError, Posting


def post_card_capture(ledger: Ledger, tenant: str, processor_txn_id: str,
                      effective_date: date, gross_minor: int, fee_minor: int,
                      our_take_minor: int, currency: str = "USD") -> Entry:
    """Dr Receivable (gross - fee), Dr Processor fees, Cr Merchant balance, Cr Revenue.

    Capture is a receivable from the processor, not cash, until payout settles.
    """
    merchant_minor = gross_minor - our_take_minor
    if min(gross_minor, fee_minor, our_take_minor) < 0 or merchant_minor < 0:
        raise LedgerError("amounts must be non-negative and our take <= gross")
    if fee_minor > gross_minor:
        raise LedgerError("fee exceeds gross")
    lines = [
        Posting("1020", DEBIT, gross_minor - fee_minor, currency),
        Posting("5010", DEBIT, fee_minor, currency),
        Posting("2010", CREDIT, merchant_minor, currency),
        Posting("4010", CREDIT, our_take_minor, currency),
    ]
    # zero-amount lines are invalid postings; drop them
    lines = [p for p in lines if p.amount_minor > 0]
    return ledger.post(tenant, f"capture:{processor_txn_id}", effective_date, lines,
                       description="card capture")
