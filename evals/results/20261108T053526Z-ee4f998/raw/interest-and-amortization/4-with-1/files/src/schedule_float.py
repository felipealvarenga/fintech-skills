"""Amortization table for display."""

def price_table(principal: float, rate: float, n: int):
    pmt = principal * rate / (1 - (1 + rate) ** -n)
    rows, balance = [], principal
    for k in range(1, n + 1):
        interest = round(balance * rate, 2)
        if k == n:
            # Last row absorbs the rounding residual so the balance ends at 0.
            amort = balance
            row_pmt = round(amort + interest, 2)
        else:
            amort = round(pmt - interest, 2)
            row_pmt = round(pmt, 2)
        balance = round(balance - amort, 2)
        rows.append({"k": k, "pmt": row_pmt, "interest": interest, "amort": amort, "balance": balance})
    return rows
