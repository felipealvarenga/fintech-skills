"""Customer export for the marketing agency.

Minimal fields only (email + masked document): the agency does not need the
full CPF, name or phone. See the pii-and-card-data rules on third-party
sharing (minimum fields) and masking (last four only).
"""
import csv
import re


def mask_document(value):
    """Mask a CPF/CNPJ, keeping only the last four alphanumerics."""
    chars = re.sub(r"[^0-9A-Za-z]", "", value or "")
    if not chars:
        return ""
    return "*" * max(len(chars) - 4, 0) + chars[-4:]


def _safe(value):
    """Neutralize spreadsheet formula injection."""
    value = value or ""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def export_customers(db, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["email", "document_masked"])
        for c in db.query("SELECT email, cpf FROM customers"):
            w.writerow([_safe(c.email), mask_document(c.cpf)])
