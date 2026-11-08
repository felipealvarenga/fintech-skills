"""Admin page: customer detail."""


def format_cpf(cpf):
    if cpf and len(cpf) == 11:
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    return cpf


def customer_detail(customer):
    return {"name": customer.name, "email": customer.email, "cpf": format_cpf(customer.cpf)}
