"""Customer and payment method models, plus data-subject deletion."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


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


class CustomerStore(Protocol):
    def delete_customer(self, customer_id: str) -> int: ...
    def list_payment_methods(self, customer_id: str) -> list[PaymentMethod]: ...
    def delete_payment_methods(self, customer_id: str) -> int: ...


class SearchIndex(Protocol):
    def delete_customer(self, customer_id: str) -> None: ...


class PaymentProcessor(Protocol):
    def delete_token(self, token: str) -> None: ...


@dataclass(frozen=True)
class DeletionReceipt:
    """Audit record. Holds no personal data: only the internal id and counts."""
    customer_id: str
    customers_deleted: int
    payment_methods_deleted: int
    tokens_revoked: int
    search_index_cleared: bool
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def delete_customer_data(
    customer_id: str,
    store: CustomerStore,
    index: SearchIndex,
    processor: PaymentProcessor,
) -> DeletionReceipt:
    """Erase a customer's personal data on their request (LGPD art. 18 / GDPR art. 17).

    Order matters so a failure can be retried safely: processor tokens are revoked
    first (they need the rows to be found), then primary rows, then the search index.
    Every step is idempotent; re-running after a partial failure finishes the job.

    Not covered here, handle in the runbook:
    - Backups: honored when they expire per the documented retention.
    - Records the law requires us to keep (e.g. fiscal/AML): retain those in a
      separate table, minimized, with their own retention, and note it in the reply.
    - Exports and third-party copies: notify processors/vendors under the DPA.
    """
    methods = store.list_payment_methods(customer_id)
    for pm in methods:
        processor.delete_token(pm.token)

    pm_deleted = store.delete_payment_methods(customer_id)
    cust_deleted = store.delete_customer(customer_id)
    index.delete_customer(customer_id)

    return DeletionReceipt(
        customer_id=customer_id,
        customers_deleted=cust_deleted,
        payment_methods_deleted=pm_deleted,
        tokens_revoked=len(methods),
        search_index_cleared=True,
    )
