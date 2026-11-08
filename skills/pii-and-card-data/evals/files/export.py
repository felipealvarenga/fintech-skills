"""Customer export for partners."""
import csv


def export_customers(db, path):
    with open(path, "w") as f:
        w = csv.writer(f)
        for c in db.query("SELECT name, email, cpf, phone FROM customers"):
            w.writerow([c.name, c.email, c.cpf, c.phone])
