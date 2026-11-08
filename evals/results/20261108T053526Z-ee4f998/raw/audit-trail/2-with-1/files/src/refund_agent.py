"""Agent that approves small refunds automatically, with an audit trail for every decision."""

POLICY_ID = "auto-refund-under-50-v1"
THRESHOLD_MINOR = 5000
AGENT_ID = "refund_agent"


def maybe_approve(refund, llm, payments, audit, request_id=None):
    """Decide a refund and record why. No audit event, no money movement.

    Events on object ("refund", refund_id), in order:
      1. agent_decision  (approve / not approved, model output, policy)
      2. refund_executed (after payments.refund succeeds, with processor reference)
    """
    refund_id = str(getattr(refund, "id", None) or refund.payment_id)
    idem_key = f"refund:{refund_id}"
    common = dict(
        object_type="refund", object_id=refund_id, actor_type="agent", actor_id=AGENT_ID,
        on_behalf_of=getattr(refund, "customer_id", None), request_id=request_id,
        idempotency_key=idem_key, policy_id=POLICY_ID, source="refund_agent.maybe_approve",
    )
    before = {"status": "requested", "amount_minor": refund.amount_minor,
              "payment_id": refund.payment_id}

    if refund.amount_minor >= THRESHOLD_MINOR:
        audit.append(action="escalated_to_human", before=before, after={"status": "pending_human"},
                     reason=f"amount_over_threshold:{THRESHOLD_MINOR}", **common)
        return False

    decision = llm.decide(refund)
    approved = decision == "approve"
    # Decision event is written BEFORE any money moves; if this raises, nothing is refunded.
    audit.append(
        action="agent_decision", before=before,
        after={"status": "approved" if approved else "not_approved", "llm_output": decision,
               "model": getattr(llm, "model", None), "threshold_minor": THRESHOLD_MINOR},
        reason="policy_auto_approve" if approved else "agent_declined", **common)
    if not approved:
        return False

    result = payments.refund(refund.payment_id, refund.amount_minor)  # TODO: pass idem_key if supported
    audit.append(
        action="refund_executed", before={"status": "approved"},
        after={"status": "refunded", "amount_minor": refund.amount_minor},
        reason="executed_after_approval",
        external_ref=str(getattr(result, "id", result)) if result is not None else None, **common)
    return True
