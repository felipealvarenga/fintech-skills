"""Short-term loan interest."""

def interest(principal: float, annual_rate: float, days: int) -> float:
    return principal * annual_rate * days / 360
