"""Contract and schedule types."""
from dataclasses import dataclass
import calendar
from datetime import date
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


def _q(value: Decimal, rounding: str) -> int:
    """Round to whole minor units with the named policy (single rounding point)."""
    return int(value.quantize(Decimal(1), rounding=rounding))


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    m += 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def sac_schedule(contract: Contract, first_due: date) -> list[dict]:
    """Constant-amortization (SAC) table. Pure; amounts in minor units.

    Amortization is round(P/n) for all but the last period, which pays the
    remaining balance, so principal parts sum to P and the final balance is 0.
    Interest per period is round(balance * i). Rate is the monthly nominal
    periodic rate from the contract; each period is one month.
    """
    rate = Decimal(contract.periodic_rate)
    n = contract.periods
    amort = _q(Decimal(contract.principal_minor) / n, contract.rounding)
    balance = contract.principal_minor
    rows = []
    for k in range(1, n + 1):
        interest = _q(Decimal(balance) * rate, contract.rounding)
        principal = balance if k == n else amort
        balance -= principal
        rows.append({
            "period": k,
            "due_date": _add_months(first_due, k - 1),
            "installment": principal + interest,
            "interest": interest,
            "principal": principal,
            "balance": balance,
        })
    assert sum(r["principal"] for r in rows) == contract.principal_minor
    assert balance == 0
    return rows


def cet(release_date: date, principal_minor: int, rows: list[dict],
        upfront_fees_minor: tuple[int, ...] = (),
        per_installment_fees_minor: tuple[int, ...] = ()) -> Decimal:
    """Annual effective total cost (CET) as the IRR of the dated cash flows.

    Net amount received = principal - upfront fees (IOF, registration, insurance
    paid at release, ...). Each installment plus per-installment fees (e.g.
    monthly insurance) is paid on its due date. Discounting uses actual days/365.

    NOT LEGALLY CONFIRMED: the exact formula, day basis, which charges enter
    it and the rounding of the disclosed figure must be confirmed by an
    accountant/lawyer against Banco Central rules before display.
    Returns an unrounded Decimal fraction (0.2683 = 26.83% a year).
    """
    received = Decimal(principal_minor - sum(upfront_fees_minor))
    extra = sum(per_installment_fees_minor)
    flows = [(Decimal((r["due_date"] - release_date).days) / 365,
              Decimal(r["installment"] + extra)) for r in rows]

    def npv(rate: Decimal) -> Decimal:
        return sum(cf / (1 + rate) ** t for t, cf in flows) - received

    lo, hi = Decimal("-0.99"), Decimal(100)
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:  # PV of payments too high -> rate too low
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
