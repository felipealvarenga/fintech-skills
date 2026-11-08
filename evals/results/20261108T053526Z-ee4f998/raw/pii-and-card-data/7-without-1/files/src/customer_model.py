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

    - Customer PII (name, email, cpf) is overwritten in place; the opaque `id`
      is kept so records that must be retained (e.g. transactions/ledger
      entries) still resolve without identifying the person.
    - Payment methods belonging to the customer are removed. The returned list
      contains only the other customers' payment methods.

    Callers must still: revoke the tokens with the payment processor, and
    delete the data from the database, backups, logs and any other stores.
    """
    customer.name = REDACTED
    customer.email = REDACTED
    customer.cpf = REDACTED
    return [pm for pm in payment_methods if pm.customer_id != customer.id]
