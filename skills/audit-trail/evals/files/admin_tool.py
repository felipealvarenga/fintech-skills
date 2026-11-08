"""Support tool: customer page. CPF is masked since the LGPD review."""

def mask_cpf(cpf: str) -> str:
    digits = "".join(ch for ch in cpf if ch.isdigit())
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def customer_page(customer):
    return {"name": customer.name, "cpf": mask_cpf(customer.cpf), "cards": [c.last4 for c in customer.cards]}
