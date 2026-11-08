"""Contract and schedule types."""
from dataclasses import dataclass
from decimal import Decimal, localcontext

import decimal

CALC_PRECISION = 40  # well above money scale; round only when posting


@dataclass(frozen=True)
class Contract:
    principal_minor: int
    periodic_rate: str  # decimal string, monthly, nominal
    periods: int
    rounding: str = "ROUND_HALF_UP"


def _round(value: Decimal, rounding: str) -> int:
    return int(value.quantize(Decimal(1), rounding=getattr(decimal, rounding)))


def _amortize(balance: int, rate: Decimal, n: int, pmt: int, rounding: str,
              start_period: int = 1, stop_when_paid: bool = False) -> list[dict]:
    """Rows for `balance` paid with installment `pmt`; the last row clears the balance."""
    rows = []
    for k in range(1, n + 1):
        interest = _round(Decimal(balance) * rate, rounding)
        if k == n or pmt - interest >= balance:
            principal = balance  # residual settles on the last installment
        else:
            principal = pmt - interest
        balance -= principal
        rows.append({
            "period": start_period + k - 1,
            "installment_minor": principal + interest,
            "interest_minor": interest,
            "principal_minor": principal,
            "balance_minor": balance,
        })
        if balance == 0:
            break
    return rows


def _pmt(balance: int, rate: Decimal, n: int, rounding: str) -> int:
    if rate == 0:
        return _round(Decimal(balance) / n, rounding)
    return _round(Decimal(balance) * rate / (1 - (1 + rate) ** -n), rounding)


def price_schedule(contract: Contract) -> list[dict]:
    """Constant-installment (Price) schedule. Amounts in minor units."""
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        rate = Decimal(contract.periodic_rate)
        pmt = _pmt(contract.principal_minor, rate, contract.periods, contract.rounding)
        return _amortize(contract.principal_minor, rate, contract.periods, pmt,
                         contract.rounding)


def price_schedule_with_prepayment(contract: Contract, prepayment_minor: int,
                                   after_period: int, mode: str) -> list[dict]:
    """Regenerate the schedule after a partial prepayment made with installment `after_period`.

    mode: "reduce_term" keeps the installment and shortens the term;
          "reduce_installment" keeps the term and lowers the installment.
    The original schedule is not modified; rows up to `after_period` are kept, with the
    prepayment shown as its own field on that row, and later rows are regenerated from
    the actual balance.
    """
    if mode not in ("reduce_term", "reduce_installment"):
        raise ValueError("mode must be 'reduce_term' or 'reduce_installment'")
    original = price_schedule(contract)
    if not 1 <= after_period < len(original):
        raise ValueError("after_period must fall inside the schedule")
    if prepayment_minor <= 0:
        raise ValueError("prepayment must be positive")

    kept = [dict(r, prepayment_minor=0) for r in original[:after_period]]
    balance = kept[-1]["balance_minor"]
    if prepayment_minor > balance:
        raise ValueError("prepayment exceeds outstanding balance")
    kept[-1]["prepayment_minor"] = prepayment_minor
    kept[-1]["balance_minor"] = balance - prepayment_minor
    new_balance = balance - prepayment_minor
    if new_balance == 0:
        return kept

    remaining = contract.periods - after_period
    with localcontext() as ctx:
        ctx.prec = CALC_PRECISION
        rate = Decimal(contract.periodic_rate)
        if mode == "reduce_term":
            pmt = original[0]["installment_minor"]
        else:
            pmt = _pmt(new_balance, rate, remaining, contract.rounding)
        tail = _amortize(new_balance, rate, remaining, pmt, contract.rounding,
                         start_period=after_period + 1)
    return kept + [dict(r, prepayment_minor=0) for r in tail]
