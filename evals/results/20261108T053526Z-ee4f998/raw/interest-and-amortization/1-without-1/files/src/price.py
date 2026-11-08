"""Price system (French amortization) installment table."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Installment:
    number: int
    payment: Decimal
    interest: Decimal
    amortization: Decimal
    balance: Decimal


def price_table(principal: Decimal, monthly_rate: Decimal, months: int) -> list[Installment]:
    """Build the Price table. Payment is rounded to cents; the last
    installment absorbs rounding so the final balance is exactly zero."""
    principal = Decimal(principal)
    monthly_rate = Decimal(monthly_rate)
    if principal <= 0 or months <= 0 or monthly_rate < 0:
        raise ValueError("principal and months must be positive, rate non-negative")

    if monthly_rate == 0:
        pmt = _q(principal / months)
    else:
        pmt = _q(principal * monthly_rate / (1 - (1 + monthly_rate) ** -months))

    rows: list[Installment] = []
    balance = _q(principal)
    for n in range(1, months + 1):
        interest = _q(balance * monthly_rate)
        if n == months:
            amort = balance
            payment = amort + interest
        else:
            payment = pmt
            amort = payment - interest
        balance -= amort
        rows.append(Installment(n, payment, interest, amort, balance))
    return rows


def _br(value: Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_table(rows: list[Installment]) -> str:
    lines = [f"{'Parcela':>7} {'Prestação':>12} {'Juros':>10} {'Amortização':>13} {'Saldo':>12}"]
    for r in rows:
        lines.append(
            f"{r.number:>7} {_br(r.payment):>12} {_br(r.interest):>10} "
            f"{_br(r.amortization):>13} {_br(r.balance):>12}"
        )
    lines.append(
        f"{'Total':>7} {_br(sum(r.payment for r in rows)):>12} "
        f"{_br(sum(r.interest for r in rows)):>10} "
        f"{_br(sum(r.amortization for r in rows)):>13}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_table(price_table(Decimal("1000.00"), Decimal("0.01"), 12)))
