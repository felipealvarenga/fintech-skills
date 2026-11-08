"""Price system (French amortization) installment table."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def price_table(principal, monthly_rate, months):
    """Return a list of rows: (n, payment, interest, amortization, balance).

    principal: loan amount; monthly_rate: e.g. "0.01" for 1% a month.
    The payment is fixed and rounded to cents; the last installment is
    adjusted so the balance ends exactly at zero.
    """
    principal = Decimal(str(principal))
    i = Decimal(str(monthly_rate))
    if principal <= 0 or months <= 0 or i < 0:
        raise ValueError("principal and months must be positive, rate non-negative")

    if i == 0:
        pmt = _q(principal / months)
    else:
        pmt = _q(principal * i / (1 - (1 + i) ** -months))

    rows = []
    balance = principal
    for n in range(1, months + 1):
        interest = _q(balance * i)
        if n == months:
            amort = balance
            payment = amort + interest
        else:
            payment = pmt
            amort = payment - interest
        balance -= amort
        rows.append((n, payment, interest, amort, balance))
    return rows


def format_table(rows):
    def br(v):
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    lines = [f"{'Nº':>3} {'Parcela':>12} {'Juros':>10} {'Amortização':>12} {'Saldo':>12}"]
    for n, p, j, a, s in rows:
        lines.append(f"{n:>3} {br(p):>12} {br(j):>10} {br(a):>12} {br(s):>12}")
    tp = sum(r[1] for r in rows)
    tj = sum(r[2] for r in rows)
    ta = sum(r[3] for r in rows)
    lines.append(f"{'Tot':>3} {br(tp):>12} {br(tj):>10} {br(ta):>12}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_table(price_table("1000.00", "0.01", 12)))
