"""Customer export for partners."""
import csv


def export_customers(db, path):
    """Write all customers (name, email, document) to a CSV at `path`."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "email", "cpf"])
        for c in db.query("SELECT name, email, cpf FROM customers"):
            w.writerow([c.name, c.email, c.cpf])
