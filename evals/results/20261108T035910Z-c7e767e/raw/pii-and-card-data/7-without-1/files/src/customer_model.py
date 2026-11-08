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
    token: str


REDACTED = "[deleted]"


def erase_customer(customer: Customer, payment_methods: list[PaymentMethod]) -> list[PaymentMethod]:
    """Erase a customer's personal data at their request.

    - Customer PII (name, email, cpf) is overwritten in place; `id` is kept so
      that records which must be retained (e.g. transactions, ledger entries
      required by financial/tax regulation) stay referentially intact.
    - All payment methods belonging to the customer are removed. Returns the
      remaining payment methods (those of other customers); the caller must
      persist this result and also revoke the tokens with the payment processor.
    """
    customer.name = REDACTED
    customer.email = REDACTED
    customer.cpf = REDACTED
    return [pm for pm in payment_methods if pm.customer_id != customer.id]
