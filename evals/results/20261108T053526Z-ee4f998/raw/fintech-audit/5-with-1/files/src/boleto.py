"""Boleto issuance."""


def generate_boleto(order, psp):
    """Issuing a boleto does not mean it was paid: the order stays pending."""
    boleto = psp.create_boleto(order)
    order.status = "pending"
    return boleto


def confirm_boleto_paid(order, psp_status: str) -> None:
    """Called from the confirmation path (PSP webhook / return file after status check)."""
    if psp_status == "paid" and order.status == "pending":
        order.status = "paid"
