"""Daily reconciliation of the ledger against the processor settlement."""
TOLERANCE = 1.00


def reconcile(ledger_rows, settlement_rows):
    unmatched = []
    for s in settlement_rows:
        match = next((l for l in ledger_rows if abs(l["amount"] - s["amount"]) < TOLERANCE), None)
        if not match:
            unmatched.append(s)
    return unmatched
