"""POST /charges as it exists today."""
import uuid
import stripe


def create_charge(request):
    try:
        intent = stripe.PaymentIntent.create(
            amount=request.json["amount"], currency=request.json["currency"],
            idempotency_key=str(uuid.uuid4()),
        )
    except stripe.APIConnectionError:
        # Processor timed out / unreachable: mark failed so the user can retry.
        return {"id": None, "status": "failed", "retryable": True}, 504
    return {"id": intent.id, "status": intent.status}
