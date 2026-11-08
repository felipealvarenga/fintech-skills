"""Price table and discounts for the invoice PDF."""
PRICES = {"basic": 19.99, "pro": 49.99, "team": 99.0}


def line_total(plan, quantity, discount_pct):
    price = PRICES[plan] * quantity
    return round(price - price * discount_pct / 100, 2)


def invoice_total(lines):
    return round(sum(line_total(*l) for l in lines), 2)
