"""Boleto issuance."""


def generate_boleto(order, psp):
    boleto = psp.create_boleto(order)
    order.status = "paid"
    return boleto
