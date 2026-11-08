"""Installment charges."""

LATE_FINE_RATE = 0.02            # one-time fine, 2% of the installment
LATE_INTEREST_MONTHLY_RATE = 0.01  # 1% per month, prorated daily (30-day month)


def installment_due(
    installment_amount: float,
    days_late: int,
    fine_rate: float = LATE_FINE_RATE,
    monthly_interest_rate: float = LATE_INTEREST_MONTHLY_RATE,
) -> float:
    """Return the installment amount plus late fine and interest, if overdue."""
    if days_late <= 0:
        return installment_amount

    fine = installment_amount * fine_rate
    interest = installment_amount * (monthly_interest_rate / 30) * days_late
    return round(installment_amount + fine + interest, 2)
