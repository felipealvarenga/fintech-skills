"""Agent that approves small refunds automatically.

Every outcome is recorded as an append-only audit event so each automatic
approval can be explained later: which policy allowed it, what the model
decided and why, what was sent to the processor, and what came back.
"""
from datetime import datetime, timezone

AUTO_APPROVE_LIMIT_MINOR = 5000
POLICY_ID = "refund-auto-approve-under-50-v1"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _event(refund, ctx, action, actor_type, actor_id, before, after, reason, **links):
    return {
        "object_type": "refund",
        "object_id": refund.payment_id,
        "action": action,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "on_behalf_of": getattr(refund, "customer_id", None),
        "before": before,
        "after": after,
        "reason": reason,
        "policy_id": POLICY_ID,
        "request_id": ctx.get("request_id"),
        "idempotency_key": ctx.get("idempotency_key"),
        "occurred_at": _now(),
        **links,
    }


def maybe_approve(refund, llm, payments, audit, ctx=None):
    """`audit.append(event)` must assign a gapless per-object `sequence` and
    `recorded_at`, and be append-only. `audit.transaction()` is a context
    manager that rolls back on error. `ctx` carries request_id and
    idempotency_key.
    """
    ctx = ctx or {}
    agent_id = ctx.get("agent_id", "refund_agent")
    amount = refund.amount_minor

    if amount >= AUTO_APPROVE_LIMIT_MINOR:
        with audit.transaction():
            audit.append(_event(
                refund, ctx, "refund.escalated", "agent", agent_id,
                {"status": "requested", "amount_minor": amount},
                {"status": "needs_human_review"},
                f"amount_at_or_above_limit:{AUTO_APPROVE_LIMIT_MINOR}"))
        return "escalated"

    result = llm.decide(refund)
    decision = getattr(result, "decision", result)
    rationale = getattr(result, "rationale", None)
    model = getattr(llm, "model_id", None)

    if decision != "approve":
        with audit.transaction():
            audit.append(_event(
                refund, ctx, "refund.not_approved", "agent", agent_id,
                {"status": "requested", "amount_minor": amount},
                {"status": "needs_human_review"},
                rationale or "model_did_not_approve",
                model_decision=decision, model_id=model))
        return "escalated"

    # 1. Approval event is committed BEFORE money moves. If it fails, no refund.
    with audit.transaction():
        audit.append(_event(
            refund, ctx, "refund.approved", "agent", agent_id,
            {"status": "requested", "amount_minor": amount},
            {"status": "approved", "amount_minor": amount},
            rationale or "model_approved",
            model_decision=decision, model_id=model))

    # 2. Execution is a separate event, linked to the processor reference.
    try:
        ref = payments.refund(refund.payment_id, amount,
                              idempotency_key=ctx.get("idempotency_key"))
    except Exception as exc:
        with audit.transaction():
            audit.append(_event(
                refund, ctx, "refund.execution_failed", "service", "payments",
                {"status": "approved"}, {"status": "failed"},
                type(exc).__name__))
        raise

    with audit.transaction():
        audit.append(_event(
            refund, ctx, "refund.executed", "service", "payments",
            {"status": "approved"}, {"status": "executed", "amount_minor": amount},
            "approved_by_agent",
            external_reference=ref))
    return "executed"
