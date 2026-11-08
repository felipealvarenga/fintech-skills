"""Signup form handler."""

def signup(form, db):
    db.execute("INSERT INTO customers (name, email) VALUES (%s, %s)", (form["name"], form["email"]))
