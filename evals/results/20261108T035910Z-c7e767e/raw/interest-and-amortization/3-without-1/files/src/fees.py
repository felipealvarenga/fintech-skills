"""Installment charges."""

LATE_FINE_RATE = 0.02            # one-time fine on any overdue installment (2%)
LATE_INTEREST_RATE_MONTHLY = 0.01  # simple interest, pro rata per day (1% / 30 days)


def installment_due(
    installment_amount: float,
    days_late: int,
    fine_rate: float = LATE_FINE_RATE,
    monthly_interest_rate: float = LATE_INTEREST_RATE_MONTHLY,
) -> float:
    if days_late <= 0:
        return installment_amount
    fine = installment_amount * fine_rate
    interest = installment_amount * monthly_interest_rate / 30 * days_late
    return round(installment_amount + fine + interest, 2)
