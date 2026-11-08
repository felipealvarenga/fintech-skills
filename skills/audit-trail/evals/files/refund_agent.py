"""Agent that approves small refunds automatically."""

def maybe_approve(refund, llm, payments):
    if refund.amount_minor < 5000 and llm.decide(refund) == "approve":
        payments.refund(refund.payment_id, refund.amount_minor)
