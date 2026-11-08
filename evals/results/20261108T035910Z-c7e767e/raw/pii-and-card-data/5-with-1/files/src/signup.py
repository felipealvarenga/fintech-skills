"""Signup form handler."""
from src import cpf as cpf_lib


def signup(form, db, crypto):
    """`crypto` is the KMS-backed service, with:
      - encrypt(str) -> bytes   (envelope encryption, per-environment key)
      - blind_index(str) -> str (keyed HMAC, for lookup/dedup without decrypting)
    """
    raw_cpf = form["cpf"]
    if not cpf_lib.is_valid(raw_cpf):
        raise ValueError("invalid CPF")
    digits = cpf_lib.normalize(raw_cpf)

    db.execute(
        "INSERT INTO customers (name, email, cpf_encrypted, cpf_hash, cpf_masked) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            form["name"],
            form["email"],
            crypto.encrypt(digits),
            crypto.blind_index(digits),
            cpf_lib.mask(digits),
        ),
    )
