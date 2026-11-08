"""Support tool: customer page."""

def customer_page(customer):
    return {"name": customer.name, "cpf": customer.cpf, "cards": [c.last4 for c in customer.cards]}
