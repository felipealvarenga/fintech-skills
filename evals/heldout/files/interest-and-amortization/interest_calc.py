"""Late fee and interest on overdue invoices."""
from datetime import datetime


def late_amount(principal, annual_rate, due_date):
    days = (datetime.now() - due_date).days
    return principal * (1 + annual_rate * days / 365)
