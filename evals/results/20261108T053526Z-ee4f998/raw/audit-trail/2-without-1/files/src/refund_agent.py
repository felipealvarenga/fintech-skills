"""Agent that approves small refunds automatically.

Every evaluation produces an audit record so each automatic approval (or
non-approval) can be explained after the fact.
"""

import time

AUTO_APPROVE_LIMIT_MINOR = 5000  # $50.00 in minor units


def _normalize(decision):
    """Accept either a plain string or an object with .action / .reason."""
    if isinstance(decision, str):
        return decision, None
    return decision.action, getattr(decision, "reason", None)


def maybe_approve(refund, llm, payments, audit_log):
    """Auto-approve small refunds; record why for every outcome.

    `audit_log` needs an `append(dict)` method (list, DB writer, etc.).
    The record is written BEFORE money moves, so a refund can never exist
    without an explanation. If the audit write fails, no refund is issued.
    """
    record = {
        "ts": time.time(),
        "payment_id": refund.payment_id,
        "amount_minor": refund.amount_minor,
        "limit_minor": AUTO_APPROVE_LIMIT_MINOR,
    }

    if refund.amount_minor >= AUTO_APPROVE_LIMIT_MINOR:
        record.update(outcome="skipped", reason="amount at or above auto-approve limit")
        audit_log.append(record)
        return False

    action, reason = _normalize(llm.decide(refund))
    record.update(llm_decision=action, llm_reason=reason)

    if action != "approve":
        record.update(outcome="not_approved", reason="model did not approve")
        audit_log.append(record)
        return False

    record.update(outcome="approved", reason="under limit and model approved")
    audit_log.append(record)  # write first; raises -> no refund
    payments.refund(refund.payment_id, refund.amount_minor)
    return True
