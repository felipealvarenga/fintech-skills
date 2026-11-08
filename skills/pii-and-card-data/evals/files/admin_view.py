"""Admin page: customer detail."""

def customer_detail(customer):
    return {"name": customer.name, "email": customer.email}
