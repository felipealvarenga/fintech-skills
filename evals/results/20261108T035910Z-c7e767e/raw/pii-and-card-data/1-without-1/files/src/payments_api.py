"""Payment endpoint."""
import logging

log = logging.getLogger("payments")

# Fields that must never reach the logs (PCI DSS forbids storing CVV, and PANs must be masked).
SENSITIVE_KEYS = {"cvv", "cvc", "card_number", "number", "pan", "password", "token", "secret"}


def _redact(obj):
    """Recursively mask sensitive fields, keeping everything else intact."""
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if str(k).lower() in SENSITIVE_KEYS else _redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


def charge(request, processor):
    payload = request.json
    log.info("charge request %s", _redact(payload))
    try:
        result = processor.charge(payload)
    except Exception:
        log.exception("charge failed with exception, request %s", _redact(payload))
        raise
    log.info("charge response %s", _redact(result))
    return result
