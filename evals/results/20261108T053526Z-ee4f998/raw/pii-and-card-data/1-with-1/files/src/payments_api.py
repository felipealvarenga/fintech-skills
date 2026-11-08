"""Payment endpoint."""
import logging

log = logging.getLogger("payments")

# Allowlists: only these top-level fields are ever logged. Anything else
# (PAN, CVV, tokens, CPF, email, names...) is dropped, including new fields.
REQUEST_LOG_FIELDS = frozenset({
    "order_id", "amount", "currency", "payment_method", "brand",
    "last4", "installments", "capture", "idempotency_key",
})
RESPONSE_LOG_FIELDS = frozenset({
    "id", "status", "decline_code", "decline_reason", "error_code",
    "response_code", "processor_response_code", "avs_result", "cvv_result",
    "network_decline_code", "amount", "currency", "brand", "last4",
    "order_id", "authorization_id", "transaction_id", "risk_score",
})
_SCALARS = (str, int, float, bool, type(None))


def safe_view(payload, allowed):
    """Return only allowlisted, scalar top-level fields of a dict."""
    if not isinstance(payload, dict):
        return {"_type": type(payload).__name__}
    return {k: v for k, v in payload.items() if k in allowed and isinstance(v, _SCALARS)}


def charge(request, processor):
    body = request.json
    log.info("charge request %s", safe_view(body, REQUEST_LOG_FIELDS))
    try:
        result = processor.charge(body)
    except Exception as exc:
        # Log the exception type only; messages from processors can echo input.
        log.error("charge error type=%s %s", type(exc).__name__,
                  safe_view(body, REQUEST_LOG_FIELDS))
        raise
    log.info("charge response %s", safe_view(result, RESPONSE_LOG_FIELDS))
    return result
