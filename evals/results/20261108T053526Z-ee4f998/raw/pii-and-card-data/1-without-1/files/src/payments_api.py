"""Payment endpoint."""
import json
import logging

log = logging.getLogger("payments")

# Fields that must never reach the logs (PCI / credentials).
_REDACT_KEYS = {
    "card_number", "number", "pan", "cvv", "cvc", "security_code",
    "expiry", "exp_month", "exp_year", "password", "token", "api_key",
    "authorization", "secret",
}


def _redact(obj):
    """Return a copy of obj with sensitive values masked."""
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if str(k).lower() in _REDACT_KEYS else _redact(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


def _dump(obj):
    return json.dumps(_redact(obj), default=str, sort_keys=True)


def charge(request, processor):
    log.info("charge request %s", _dump(request.json))
    try:
        result = processor.charge(request.json)
    except Exception:
        log.exception("charge failed with exception")
        raise
    log.info("charge response %s", _dump(result))
    return result
