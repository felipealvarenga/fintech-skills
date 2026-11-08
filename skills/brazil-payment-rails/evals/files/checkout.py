"""Checkout with boleto."""
from dataclasses import dataclass


@dataclass
class Order:
    id: str
    status: str = "pending"


def generate_boleto(order: Order, psp) -> dict:
    boleto = psp.create_boleto(order)
    return {"linha_digitavel": boleto["linha_digitavel"], "nosso_numero": boleto["nosso_numero"], "vencimento": boleto["vencimento"]}
