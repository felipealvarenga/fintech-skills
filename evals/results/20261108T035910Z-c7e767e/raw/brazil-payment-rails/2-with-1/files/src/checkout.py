"""Checkout with boleto."""
from dataclasses import dataclass


@dataclass
class Order:
    id: str
    status: str = "pending"
    nosso_numero: str | None = None


def generate_boleto(order: Order, psp) -> dict:
    """Issue a boleto. The order stays pending until the bank confirms payment."""
    boleto = psp.create_boleto(order)
    order.nosso_numero = boleto["nosso_numero"]
    return {"linha_digitavel": boleto["linha_digitavel"], "nosso_numero": boleto["nosso_numero"], "vencimento": boleto["vencimento"]}


def confirm_boleto_payment(order: Order, nosso_numero: str) -> bool:
    """Call from the return-file (CNAB retorno) or PSP webhook handler once the
    bank reports the boleto as paid. Matches by nosso número (ignoring leading
    zeros) and is idempotent. Returns True if the order is paid after the call."""
    if order.nosso_numero is None or order.nosso_numero.lstrip("0") != nosso_numero.lstrip("0"):
        return False
    order.status = "paid"
    return True


def can_download(order: Order) -> bool:
    """The product is released only for paid orders."""
    return order.status == "paid"
