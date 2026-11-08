"""Boleto issuance."""


def generate_boleto(order, psp):
    boleto = psp.create_boleto(order)
    # Issuing a boleto is not payment; mark paid only on the PSP's payment confirmation.
    order.status = "awaiting_payment"
    return boleto
