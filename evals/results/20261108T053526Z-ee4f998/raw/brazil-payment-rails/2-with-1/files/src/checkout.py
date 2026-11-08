"""Checkout with boleto."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    id: str
    status: str = "pending"
    nosso_numero: Optional[str] = None
    linha_digitavel: Optional[str] = None


def generate_boleto(order: Order, psp) -> dict:
    """Issue the boleto. The order stays pending until the bank confirms payment."""
    boleto = psp.create_boleto(order)
    order.nosso_numero = str(boleto["nosso_numero"])
    order.linha_digitavel = boleto["linha_digitavel"]
    return {"linha_digitavel": boleto["linha_digitavel"], "nosso_numero": boleto["nosso_numero"], "vencimento": boleto["vencimento"]}


def confirm_boleto_payment(order: Order, nosso_numero: str) -> bool:
    """Call from the return-file (CNAB retorno) or PSP webhook handler once the
    bank reports the boleto as paid. Matches by nosso numero (string, so leading
    zeros are kept). Idempotent. Returns True if the order was newly marked paid."""
    if order.nosso_numero is None or str(nosso_numero) != order.nosso_numero:
        raise ValueError("nosso_numero does not match this order")
    if order.status == "paid":
        return False
    order.status = "paid"
    return True


def can_download(order: Order) -> bool:
    """Product download is released only for paid orders."""
    return order.status == "paid"
