"""POST /charges: safe to retry; the same Idempotency-Key never charges twice."""
import stripe


def create_charge(request):
    # The key must be chosen by the client once per logical charge and reused
    # on every retry. Generating it server-side per request defeats idempotency.
    key = (request.headers.get("Idempotency-Key") or "").strip()
    if not key or len(key) > 255:
        return {"error": "Idempotency-Key header is required (max 255 chars)"}, 400

    body = request.json or {}
    amount, currency = body.get("amount"), body.get("currency")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or not currency:
        return {"error": "amount (positive integer, minor units) and currency are required"}, 400

    try:
        # Stripe replays the original response for a repeated key with identical
        # params, and rejects the same key with different params.
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            idempotency_key=key,
        )
    except stripe.error.IdempotencyError:
        return {"error": "Idempotency-Key was already used with different parameters"}, 409

    return {"id": intent.id, "status": intent.status}
