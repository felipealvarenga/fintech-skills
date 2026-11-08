"""Signup form handler."""
from src import cpf as cpf_lib


def signup(form, db, vault):
    """`vault` wraps the KMS: encrypt(str) -> bytes (envelope encryption) and
    blind_index(str) -> str (keyed hash, for duplicate lookup)."""
    cpf = cpf_lib.normalize(form.get("cpf"))
    if not cpf_lib.is_valid(cpf):
        raise ValueError("invalid CPF")  # never echo the value back or log it
    db.execute(
        "INSERT INTO customers (name, email, cpf_encrypted, cpf_hash, cpf_masked)"
        " VALUES (%s, %s, %s, %s, %s)",
        (
            form["name"],
            form["email"],
            vault.encrypt(cpf),
            vault.blind_index(cpf),
            cpf_lib.mask(cpf),
        ),
    )
