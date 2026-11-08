"""Settlement dates."""
from datetime import datetime, timedelta


def settlement_date(amount: int) -> datetime:
    return datetime.now() + timedelta(days=1)
