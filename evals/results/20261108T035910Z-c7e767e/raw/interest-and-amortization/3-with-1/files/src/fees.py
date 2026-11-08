"""Installment charges."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

# Defaults are placeholders: confirm against the contract / local law.
LATE_FINE_RATE = Decimal("0.02")          # one-time fine on the overdue amount
LATE_INTEREST_MONTHLY = Decimal("0.01")   # simple interest, 1% a month
DAYS_PER_MONTH = Decimal("30")            # pro rata daily: monthly rate / 30


@dataclass(frozen=True)
class InstallmentCharges:
    installment: Decimal
    late_fine: Decimal
    late_interest: Decimal

    @property
    def total(self) -> Decimal:
        return self.installment + self.late_fine + self.late_interest


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def installment_charges(
    installment_amount,
    days_late: int,
    fine_rate: Decimal = LATE_FINE_RATE,
    monthly_interest_rate: Decimal = LATE_INTEREST_MONTHLY,
) -> InstallmentCharges:
    """Break down what is owed; fine and interest stay separate lines."""
    amount = Decimal(str(installment_amount))
    if days_late <= 0:
        zero = Decimal("0.00")
        return InstallmentCharges(_money(amount), zero, zero)
    fine = _money(amount * fine_rate)
    # Single rounding point: interest accrues at full precision, rounded once.
    interest = _money(amount * monthly_interest_rate / DAYS_PER_MONTH * days_late)
    return InstallmentCharges(_money(amount), fine, interest)


def installment_due(installment_amount: float, days_late: int) -> float:
    """Total to pay: installment + late fine + late interest."""
    return float(installment_charges(installment_amount, days_late).total)
