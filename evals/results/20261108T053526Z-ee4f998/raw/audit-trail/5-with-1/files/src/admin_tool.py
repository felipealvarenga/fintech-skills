"""Support tool: customer page. CPF is masked by default since the LGPD review.

Support reps can reveal the full CPF, but only with a reason code and only if the
audit event is recorded first (audit-trail rules 1, 3, 5, 6).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol
import uuid

REASON_CODES = frozenset({
    "IDENTITY_VERIFICATION",
    "FRAUD_INVESTIGATION",
    "CUSTOMER_REQUEST",
    "REGULATORY_REQUEST",
})


class AuditSink(Protocol):
    """Append-only sink. append() must raise on failure; it must not swallow errors.

    Implementations should assign the per-object `sequence` and `recorded_at`
    from the database, in the same transaction as the write.
    """
    def append(self, event: dict) -> None: ...


@dataclass(frozen=True)
class Actor:
    actor_id: str
    actor_type: str = "user"  # user, service, agent, system


class RevealDenied(Exception):
    pass


def mask_cpf(cpf: str) -> str:
    digits = "".join(ch for ch in cpf if ch.isdigit())
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def format_cpf(cpf: str) -> str:
    d = "".join(ch for ch in cpf if ch.isdigit())
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"


def reveal_cpf(customer, actor: Actor, reason_code: str, reason_text: str,
               request_id: str, audit: AuditSink,
               ticket: Optional[str] = None) -> str:
    """Return the full CPF. The audit event is appended first; if that fails,
    nothing is revealed. The event never contains the full CPF."""
    if reason_code not in REASON_CODES:
        raise RevealDenied("a valid reason code is required")
    if not (reason_text and reason_text.strip()) and not ticket:
        raise RevealDenied("a reason text or ticket reference is required")
    if not request_id:
        raise RevealDenied("request_id is required")

    audit.append({
        "event_id": str(uuid.uuid4()),
        "object_type": "customer",
        "object_id": getattr(customer, "id", None),
        "action": "cpf.reveal",
        "actor_type": actor.actor_type,
        "actor_id": actor.actor_id,
        "before": {"cpf": mask_cpf(customer.cpf)},
        "after": {"cpf": mask_cpf(customer.cpf)},  # nothing changes; value is not stored
        "reason_code": reason_code,
        "reason": reason_text,
        "ticket": ticket,
        "request_id": request_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "admin_tool",
    })
    return format_cpf(customer.cpf)


def customer_page(customer, reveal: Optional[dict] = None):
    """`reveal` = dict(actor, reason_code, reason_text, request_id, audit[, ticket]).
    Without it, the CPF stays masked."""
    cpf = mask_cpf(customer.cpf)
    if reveal is not None:
        cpf = reveal_cpf(customer, **reveal)
    return {"name": customer.name, "cpf": cpf, "cards": [c.last4 for c in customer.cards]}
