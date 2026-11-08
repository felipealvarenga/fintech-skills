"""POST /charges.

Retry safety: the client must send an `Idempotency-Key` header and reuse the
same value when retrying the same logical charge. The key is forwarded to
Stripe, which returns the original result for repeated keys instead of
creating a second PaymentIntent.
"""
import stripe

MAX_KEY_LEN = 255  # Stripe's limit for idempotency keys


def create_charge(request):
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if not key or len(key) > MAX_KEY_LEN:
        return {"error": "Idempotency-Key header is required (max 255 chars)"}, 400

    body = request.json or {}
    amount, currency = body.get("amount"), body.get("currency")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or not currency:
        return {"error": "amount (positive integer, minor units) and currency are required"}, 400

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            idempotency_key=key,
        )
    except stripe.error.IdempotencyError:
        # Same key reused with different parameters: a client bug, not a retry.
        return {"error": "Idempotency-Key was already used with different parameters"}, 409

    return {"id": intent.id, "status": intent.status}
