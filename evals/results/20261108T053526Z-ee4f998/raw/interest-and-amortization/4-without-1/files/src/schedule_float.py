"""Amortization table for display."""

def price_table(principal: float, rate: float, n: int):
    pmt = principal * rate / (1 - (1 + rate) ** -n)
    rows, balance = [], principal
    for k in range(1, n + 1):
        interest = round(balance * rate, 2)
        amort = round(pmt - interest, 2)
        row_pmt = round(pmt, 2)
        if k == n:
            # Absorb accumulated rounding drift so the schedule ends at zero.
            amort = balance
            row_pmt = round(interest + amort, 2)
            balance = 0.0
        else:
            balance = round(balance - amort, 2)
        rows.append({"k": k, "pmt": row_pmt, "interest": interest, "amort": amort, "balance": balance})
    return rows
