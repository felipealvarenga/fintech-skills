"""Erasure of a customer and their payment methods (LGPD/GDPR deletion request).

Storage is injected so the same flow works over any database. Order matters:
external copies first (processor tokens, search index), primary rows last, so a
failure midway leaves the customer row in place and the request can be retried.
Every step is idempotent.
"""
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from src.customer_model import Customer, PaymentMethod


class CustomerStore(Protocol):
    def get(self, customer_id: str) -> Customer | None: ...
    def delete(self, customer_id: str) -> None: ...


class PaymentMethodStore(Protocol):
    def list_for_customer(self, customer_id: str) -> list[PaymentMethod]: ...
    def delete_for_customer(self, customer_id: str) -> int: ...


class SearchIndex(Protocol):
    def remove_customer(self, customer_id: str) -> None: ...


class ProcessorClient(Protocol):
    def delete_token(self, token: str) -> None:
        """Must treat an already-deleted token as success."""


class AuditLog(Protocol):
    def record(self, event: dict) -> None: ...


@dataclass(frozen=True)
class DeletionReceipt:
    subject_ref: str  # salted-free one-way ref; the id itself is not logged
    customer_deleted: bool
    payment_methods_deleted: int
    completed_at: str


def _subject_ref(customer_id: str) -> str:
    return hashlib.sha256(customer_id.encode()).hexdigest()[:16]


def delete_customer(
    customer_id: str,
    *,
    customers: CustomerStore,
    payment_methods: PaymentMethodStore,
    index: SearchIndex,
    processor: ProcessorClient,
    audit: AuditLog,
) -> DeletionReceipt:
    """Erase the customer's personal data. Safe to call again after a failure.

    Not covered here (handle in the runbook): records the law requires us to
    keep (e.g. transaction ledgers) must be anonymized by their owners, and
    backups are purged when they expire per the documented retention.
    """
    existing = customers.get(customer_id)
    methods = payment_methods.list_for_customer(customer_id)

    # 1. External copies. Raises on failure -> nothing local is deleted yet.
    for pm in methods:
        processor.delete_token(pm.token)
    index.remove_customer(customer_id)

    # 2. Primary rows.
    count = payment_methods.delete_for_customer(customer_id)
    customers.delete(customer_id)

    receipt = DeletionReceipt(
        subject_ref=_subject_ref(customer_id),
        customer_deleted=existing is not None,
        payment_methods_deleted=count,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    # Audit proves the erasure happened without retaining personal data.
    audit.record({"event": "customer_erased", "subject_ref": receipt.subject_ref,
                  "payment_methods_deleted": count, "at": receipt.completed_at})
    return receipt
