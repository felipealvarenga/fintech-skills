"""Boleto issuance."""


def generate_boleto(order, psp):
    boleto = psp.create_boleto(order)
    order.status = "pending"  # marked paid only by the confirmed payment/return-file path
    return boleto
