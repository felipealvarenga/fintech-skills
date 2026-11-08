"""Admin page: customer detail."""

def customer_detail(customer):
    # CPF is masked by default; the full value is never sent to the admin page.
    return {"name": customer.name, "email": customer.email, "cpf": customer.cpf_masked}
