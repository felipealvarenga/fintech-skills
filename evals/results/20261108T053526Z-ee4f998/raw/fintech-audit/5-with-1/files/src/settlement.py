"""Settlement dates (D+1 business day, UTC, injected clock)."""
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable


def settlement_date(
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    holidays: Iterable[date] = (),
) -> date:
    """Next business day after `now()`, skipping weekends and the given holidays."""
    skip = set(holidays)
    d = now().date() + timedelta(days=1)
    while d.weekday() >= 5 or d in skip:
        d += timedelta(days=1)
    return d
