"""Boleto issuance."""


def generate_boleto(order, psp):
    boleto = psp.create_boleto(order)
    # Issuing a boleto does not mean it was paid; mark paid only on PSP payment confirmation.
    order.status = "awaiting_payment"
    return boleto
