"""Customer and payment method models."""
from dataclasses import dataclass


@dataclass
class Customer:
    id: str
    name: str
    email: str
    cpf: str


@dataclass
class PaymentMethod:
    customer_id: str
    brand: str
    last4: str
    token: str  # processor-issued token; the only thing needed to charge again
    exp_month: int | None = None
    exp_year: int | None = None

    # The full card number (PAN) and CVV must never be added here: the PAN goes
    # browser -> processor via hosted fields, and the CVV is never stored.

    @property
    def masked(self) -> str:
        return f"{self.brand} •••• {self.last4}"

    def can_charge_one_click(self, today=None) -> bool:
        """True if the saved token can be reused (has a token and is not expired)."""
        from datetime import date

        if not self.token:
            return False
        if self.exp_month is None or self.exp_year is None:
            return True
        today = today or date.today()
        return (self.exp_year, self.exp_month) >= (today.year, today.month)
