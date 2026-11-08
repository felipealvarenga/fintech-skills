"""Settlement dates (D+1 business day, UTC, injectable clock)."""
from datetime import datetime, timedelta, timezone
from typing import Callable, Collection


def settlement_date(
    amount: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    holidays: Collection = (),
) -> datetime:
    d = now() + timedelta(days=1)
    while d.weekday() >= 5 or d.date() in holidays:
        d += timedelta(days=1)
    return d
