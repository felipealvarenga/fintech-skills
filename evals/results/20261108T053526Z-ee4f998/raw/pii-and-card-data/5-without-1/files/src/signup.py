"""Signup form handler."""
import re


def normalize_cpf(raw):
    """Strip formatting and validate a CPF (11 digits + check digits). Returns digits only."""
    cpf = re.sub(r"\D", "", raw or "")
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValueError("Invalid CPF")
    for i in (9, 10):
        total = sum(int(d) * w for d, w in zip(cpf[:i], range(i + 1, 1, -1)))
        check = (total * 10 % 11) % 10
        if check != int(cpf[i]):
            raise ValueError("Invalid CPF")
    return cpf


def signup(form, db):
    cpf = normalize_cpf(form["cpf"])
    db.execute(
        "INSERT INTO customers (name, email, cpf) VALUES (%s, %s, %s)",
        (form["name"], form["email"], cpf),
    )
