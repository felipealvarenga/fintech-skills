"""Double-entry model of a card capture. All amounts are integer cents."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    account: str
    debit: int = 0
    credit: int = 0


def capture_entries(amount: int, processor_fee: int, our_share: int) -> list[Entry]:
    """Journal entries for a captured card payment.

    The merchant is owed amount - our_share. The processor fee is our cost,
    paid out of our_share (it is not deducted from the merchant).
    """
    if min(amount, processor_fee, our_share) < 0:
        raise ValueError("amounts must be non-negative")
    if our_share > amount:
        raise ValueError("our share cannot exceed the captured amount")

    merchant_owed = amount - our_share
    entries = [
        # Processor settles to us net of its fee.
        Entry("processor_receivable", debit=amount - processor_fee),
        Entry("processor_fee_expense", debit=processor_fee),
        Entry("merchant_payable", credit=merchant_owed),
        Entry("platform_revenue", credit=our_share),
    ]
    assert sum(e.debit for e in entries) == sum(e.credit for e in entries)
    return entries
