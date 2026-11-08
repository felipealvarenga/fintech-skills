"""Installment charges.

Late charges are kept as separate lines (fine, late interest) so they can be
posted to separate accounts, disclosed and disputed. ``installment_due`` returns
their sum with the installment.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

# Assumed defaults (confirm against the contract):
# - fine: one-off 2% of the installment, charged once when any day late.
# - late interest: simple interest, 1% per month, pro rata per day on a
#   30-day month (day count 30 days/month), no compounding.
DEFAULT_FINE_RATE = Decimal("0.02")
DEFAULT_MONTHLY_LATE_RATE = Decimal("0.01")
DAYS_PER_MONTH = Decimal(30)


@dataclass(frozen=True)
class InstallmentCharges:
    installment: Decimal
    late_interest: Decimal
    fine: Decimal

    @property
    def total(self) -> Decimal:
        return self.installment + self.late_interest + self.fine


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def installment_charges(
    installment_amount: Decimal | str | int,
    days_late: int,
    fine_rate: Decimal = DEFAULT_FINE_RATE,
    monthly_late_rate: Decimal = DEFAULT_MONTHLY_LATE_RATE,
) -> InstallmentCharges:
    """Return installment, late interest and fine as separate lines."""
    amount = Decimal(str(installment_amount))
    if days_late <= 0:
        zero = Decimal("0.00")
        return InstallmentCharges(_money(amount), zero, zero)

    # Compute at full precision; round only the posted values.
    interest = amount * monthly_late_rate * Decimal(days_late) / DAYS_PER_MONTH
    fine = amount * fine_rate
    return InstallmentCharges(_money(amount), _money(interest), _money(fine))


def installment_due(
    installment_amount: Decimal | str | int,
    days_late: int,
    fine_rate: Decimal = DEFAULT_FINE_RATE,
    monthly_late_rate: Decimal = DEFAULT_MONTHLY_LATE_RATE,
) -> Decimal:
    """Installment plus late interest plus fine."""
    return installment_charges(
        installment_amount, days_late, fine_rate, monthly_late_rate
    ).total
