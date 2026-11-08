"""Customer export for partners."""
import csv


def export_customers(db, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "email", "cpf", "phone"])
        for c in db.query("SELECT name, email, cpf, phone FROM customers"):
            w.writerow([c.name, c.email, c.cpf, c.phone])
