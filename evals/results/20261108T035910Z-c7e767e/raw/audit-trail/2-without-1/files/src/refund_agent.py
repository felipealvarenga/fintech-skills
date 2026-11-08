"""Agent that approves small refunds automatically.

Every decision (approved or not) is written to an audit log so it can be
explained later: what the refund was, which rule applied, what the model said,
and whether money actually moved.
"""
import json
import logging
import time

AUTO_APPROVE_LIMIT_MINOR = 5000  # $50.00, exclusive

audit_logger = logging.getLogger("refund_agent.audit")


def _record(audit, entry):
    entry["ts"] = time.time()
    if audit is not None:
        audit(entry)
    else:
        audit_logger.info(json.dumps(entry, default=str, sort_keys=True))


def maybe_approve(refund, llm, payments, audit=None):
    """Auto-approve refunds under the limit if the model agrees.

    `audit` is an optional callable taking a dict; defaults to JSON log lines
    on the "refund_agent.audit" logger. It is called before money moves, so a
    refund can never be issued without a decision record.
    """
    entry = {
        "payment_id": refund.payment_id,
        "amount_minor": refund.amount_minor,
        "limit_minor": AUTO_APPROVE_LIMIT_MINOR,
    }

    if refund.amount_minor >= AUTO_APPROVE_LIMIT_MINOR:
        _record(audit, {**entry, "decision": "skipped",
                        "reason": "amount at or above auto-approve limit"})
        return False

    decision = llm.decide(refund)
    # Capture model rationale if the llm exposes one (not all implementations do).
    rationale = getattr(llm, "last_rationale", None)
    entry.update(decision=decision, model_rationale=rationale)

    if decision != "approve":
        _record(audit, {**entry, "reason": "model did not approve"})
        return False

    _record(audit, {**entry, "reason": "under limit and model approved",
                    "status": "refund_requested"})
    payments.refund(refund.payment_id, refund.amount_minor)
    _record(audit, {**entry, "status": "refund_issued"})
    return True
