"""Short-term loan interest."""

def interest(principal: float, annual_rate: float, days: int) -> float:
    return principal * annual_rate * days / 360


def bridge_loan_interest(principal: float) -> float:
    """Interest for a 45-day bridge loan at 18% per year."""
    return interest(principal, 0.18, 45)
