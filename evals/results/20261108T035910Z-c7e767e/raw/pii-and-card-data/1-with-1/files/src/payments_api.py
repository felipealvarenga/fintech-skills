"""Payment endpoint."""
import logging

log = logging.getLogger("payments")

# Allowlists: only these top-level fields are ever logged. Anything else
# (PAN, CVV, CPF, tokens, names, emails, free-text messages) is dropped.
REQUEST_ALLOWED = ("order_id", "amount", "currency", "payment_method_type", "brand", "last4")
RESPONSE_ALLOWED = (
    "id", "status", "decline_code", "error_code",
    "processor_response_code", "avs_result", "amount", "currency",
)


def _safe(value):
    """Scalars only, truncated, so nested objects cannot smuggle data in."""
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, str):
        return value[:64]
    return "<omitted>"


def redact(payload, allowed):
    if not isinstance(payload, dict):
        return {}
    out = {k: _safe(payload[k]) for k in allowed if k in payload}
    # last4 must really be four digits, otherwise a full PAN could slip in.
    if "last4" in out and not (isinstance(out["last4"], str) and len(out["last4"]) == 4 and out["last4"].isdigit()):
        out["last4"] = "<invalid>"
    return out


def charge(request, processor):
    log.info("charge request %s", redact(request.json, REQUEST_ALLOWED))
    try:
        result = processor.charge(request.json)
    except Exception as exc:
        # Log the exception type only; messages can echo request data.
        log.error("charge failed type=%s", type(exc).__name__)
        raise
    log.info("charge response %s", redact(result, RESPONSE_ALLOWED))
    return result
