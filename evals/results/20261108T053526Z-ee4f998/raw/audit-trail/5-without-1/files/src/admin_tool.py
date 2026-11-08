"""Support tool: customer page. Support reps see the full CPF (previously masked after the LGPD review)."""

def mask_cpf(cpf: str) -> str:
    digits = "".join(ch for ch in cpf if ch.isdigit())
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def format_cpf(cpf: str) -> str:
    digits = "".join(ch for ch in cpf if ch.isdigit())
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def customer_page(customer):
    return {"name": customer.name, "cpf": format_cpf(customer.cpf), "cards": [c.last4 for c in customer.cards]}
