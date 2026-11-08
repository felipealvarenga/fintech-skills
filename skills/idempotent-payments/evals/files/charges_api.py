"""POST /charges as it exists today."""
import uuid
import stripe


def create_charge(request):
    intent = stripe.PaymentIntent.create(
        amount=request.json["amount"], currency=request.json["currency"],
        idempotency_key=str(uuid.uuid4()),
    )
    return {"id": intent.id, "status": intent.status}
