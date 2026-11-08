"""Customer export for the marketing agency.

Minimization (pii-and-card-data rule 7): the agency gets name, email and a
masked document (last four digits only). Full CPF and phone are never exported.
"""
import csv
import re

HEADER = ["name", "email", "document_masked"]


def mask_document(value):
    """Mask a CPF/CNPJ, keeping only the last four alphanumeric characters."""
    if not value:
        return ""
    chars = re.sub(r"[^0-9A-Za-z]", "", str(value))
    if len(chars) <= 4:
        return "*" * len(chars)
    return "*" * (len(chars) - 4) + chars[-4:]


def _safe(cell):
    """Neutralize spreadsheet formula injection."""
    s = "" if cell is None else str(cell)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def export_customers(db, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for c in db.query("SELECT name, email, cpf FROM customers"):
            w.writerow([_safe(c.name), _safe(c.email), mask_document(c.cpf)])
