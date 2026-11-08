"""Contract and schedule types."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Contract:
    principal_minor: int
    periodic_rate: str  # decimal string, monthly, nominal
    periods: int
    rounding: str = "ROUND_HALF_UP"


def price_schedule(contract: Contract) -> list[dict]:
    raise NotImplementedError
