"""Admin page: customer detail."""


def customer_detail(customer):
    # CPF is masked by default; the admin page never reads or decrypts the full value.
    # A reveal flow needs its own permission, stated purpose and audit record.
    return {"name": customer.name, "email": customer.email, "cpf": customer.cpf_masked}
