"""Signup form handler."""
import re


def normalize_cpf(raw):
    """Strip formatting and return the 11 CPF digits, or raise ValueError."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) != 11 or digits == digits[0] * 11:
        raise ValueError("Invalid CPF")
    for n in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:n], range(n + 1, 1, -1)))
        check = (total * 10 % 11) % 10
        if check != int(digits[n]):
            raise ValueError("Invalid CPF")
    return digits


def signup(form, db):
    cpf = normalize_cpf(form.get("cpf"))
    db.execute(
        "INSERT INTO customers (name, email, cpf) VALUES (%s, %s, %s)",
        (form["name"], form["email"], cpf),
    )
