"""Contract and schedule types."""
from dataclasses import dataclass
import decimal
from decimal import Decimal, getcontext


@dataclass(frozen=True)
class Contract:
    principal_minor: int
    periodic_rate: str  # decimal string, monthly, nominal
    periods: int
    rounding: str = "ROUND_HALF_UP"


def price_schedule(contract: Contract) -> list[dict]:
    raise NotImplementedError


getcontext().prec = 40
_SCALE = Decimal(1).scaleb(-2)


def _money(minor: int) -> Decimal:
    return Decimal(minor).scaleb(-2)


def _round_minor(value: Decimal, rounding: str) -> int:
    """Round a value in minor units to an integer with the named policy."""
    return int(value.quantize(Decimal(1), rounding=getattr(decimal, rounding)))


def sac_schedule(contract: Contract) -> list[dict]:
    """Constant-amortization schedule. All amounts in minor units.

    amortization = round(P / n) for periods 1..n-1; the last pays the remainder.
    interest = round(balance * i) per period. Pure function, no I/O.
    """
    i = Decimal(contract.periodic_rate)
    n = contract.periods
    amort = _round_minor(Decimal(contract.principal_minor) / n, contract.rounding)
    balance = contract.principal_minor
    rows = []
    for k in range(1, n + 1):
        interest = _round_minor(Decimal(balance) * i, contract.rounding)
        principal = balance if k == n else amort
        balance -= principal
        rows.append({
            "period": k,
            "installment": principal + interest,
            "interest": interest,
            "principal": principal,
            "balance": balance,
        })
    assert sum(r["principal"] for r in rows) == contract.principal_minor
    assert rows[-1]["balance"] == 0
    return rows


def cet(contract: Contract, rows: list[dict], upfront_costs_minor: int = 0,
        periodic_costs_minor: list[int] | None = None) -> dict:
    """Total effective cost as the periodic IRR of the borrower's cash flows,
    annualised as (1 + irr)^12 - 1.

    Costs are separate lines: upfront_costs_minor (IOF, tariffs, financed or not)
    reduce the net amount received at t=0; periodic_costs_minor (insurance, fees)
    are added to each installment. Periods are assumed equal monthly intervals.
    NOTE: the regulatory formula (day count, 365-day year, which costs enter) must
    be confirmed by an accountant/lawyer; this is the engineering skeleton.
    """
    periodic = periodic_costs_minor or [0] * len(rows)
    flows = [Decimal(contract.principal_minor - upfront_costs_minor)]
    flows += [-Decimal(r["installment"] + c) for r, c in zip(rows, periodic)]

    def npv(rate: Decimal) -> Decimal:
        return sum(f / (1 + rate) ** t for t, f in enumerate(flows))

    lo, hi = Decimal("0"), Decimal("1")  # monthly rate bracket
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    monthly = (lo + hi) / 2
    annual = (1 + monthly) ** 12 - 1
    return {"monthly": monthly, "annual": annual}
