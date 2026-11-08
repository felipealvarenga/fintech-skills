"""Contract and schedule types."""
import decimal
from dataclasses import dataclass
from decimal import Decimal, localcontext

REDUCE_INSTALLMENT = "reduce_installment"  # same term, smaller installment
SHORTEN_TERM = "shorten_term"  # same installment, fewer periods


@dataclass(frozen=True)
class Prepayment:
    """Extra principal paid right after the installment of `period` is paid."""
    period: int
    amount_minor: int
    mode: str  # REDUCE_INSTALLMENT or SHORTEN_TERM; the contract must choose


@dataclass(frozen=True)
class Contract:
    principal_minor: int
    periodic_rate: str  # decimal string, monthly, nominal
    periods: int
    rounding: str = "ROUND_HALF_UP"


def _pmt(balance: Decimal, i: Decimal, n: int) -> Decimal:
    if i == 0:
        return balance / n
    return balance * i / (1 - (1 + i) ** -n)


def price_schedule(contract: Contract,
                   prepayments: tuple[Prepayment, ...] = ()) -> list[dict]:
    """Constant-installment schedule in minor units (centavos).

    Pure function. Each row: period, installment, interest, principal,
    prepayment, balance. A prepayment appears on the row of its period and
    the schedule continues from the reduced balance. The last installment
    absorbs the rounding residual, so sum(principal) + sum(prepayment)
    equals the principal exactly and the final balance is 0.
    """
    by_period = {p.period: p for p in prepayments}
    if len(by_period) != len(prepayments):
        raise ValueError("at most one prepayment per period")
    rounding = getattr(decimal, contract.rounding)

    with localcontext() as ctx:
        ctx.prec = 40

        def q(x: Decimal) -> int:
            return int(x.quantize(Decimal(1), rounding=rounding))

        i = Decimal(contract.periodic_rate)
        balance = contract.principal_minor
        n = contract.periods
        pmt = q(_pmt(Decimal(balance), i, n))
        rows = []

        for period in range(1, n + 1):
            interest = q(Decimal(balance) * i)
            principal = pmt - interest
            if period == n or principal >= balance:
                principal = balance  # last installment settles the residual
            balance -= principal
            row = {
                "period": period,
                "installment": principal + interest,
                "interest": interest,
                "principal": principal,
                "prepayment": 0,
                "balance": balance,
            }
            rows.append(row)
            if balance == 0:
                break

            pre = by_period.get(period)
            if pre:
                if pre.mode not in (REDUCE_INSTALLMENT, SHORTEN_TERM):
                    raise ValueError(f"unknown prepayment mode: {pre.mode}")
                amount = min(pre.amount_minor, balance)
                balance -= amount
                row["prepayment"] = amount
                row["balance"] = balance
                if balance == 0:
                    break
                if pre.mode == REDUCE_INSTALLMENT:
                    pmt = q(_pmt(Decimal(balance), i, n - period))
                # SHORTEN_TERM keeps pmt; loop ends when balance is paid off

        return rows
