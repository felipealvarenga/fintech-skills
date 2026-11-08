"""Settlement dates."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BR_TZ = ZoneInfo("America/Sao_Paulo")


def settlement_date(amount: int, now: datetime | None = None) -> datetime:
    """D+1 business day in Brazil time. `now` is injectable for testing.

    Weekends are skipped; bank holidays are not handled here.
    """
    now = now.astimezone(BR_TZ) if now else datetime.now(BR_TZ)
    d = now + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
