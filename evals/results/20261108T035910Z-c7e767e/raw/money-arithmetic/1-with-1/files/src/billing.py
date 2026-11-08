"""Invoice splitting on integer minor units. Replaces the float path in billing_float.py."""
import sqlite3

from money import Money, allocate, to_minor

PARTNER_RATIOS = {"partner_a": 50, "partner_b": 30, "partner_c": 20}

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_shares (
    invoice_id   TEXT    NOT NULL,
    partner      TEXT    NOT NULL,
    amount_minor INTEGER NOT NULL,
    currency     TEXT    NOT NULL,
    PRIMARY KEY (invoice_id, partner)
)"""


def split_invoice(total: Money, ratios: dict[str, int]) -> dict[str, Money]:
    parts = allocate(total.minor, list(ratios.values()))
    return {p: Money(m, total.currency) for p, m in zip(ratios, parts)}


def split_and_store(conn: sqlite3.Connection, invoice_id: str, total: Money,
                    ratios: dict[str, int] = PARTNER_RATIOS) -> dict[str, Money]:
    shares = split_invoice(total, ratios)
    conn.execute(SCHEMA)
    with conn:  # one transaction: all shares or none
        conn.executemany(
            "INSERT INTO invoice_shares VALUES (?, ?, ?, ?)",
            [(invoice_id, p, s.minor, s.currency) for p, s in shares.items()])
    return shares


if __name__ == "__main__":
    conn = sqlite3.connect(":memory:")
    for p, s in split_and_store(conn, "INV-1", Money(to_minor("100.00", "BRL"), "BRL")).items():
        print(p, s)
