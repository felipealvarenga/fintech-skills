"""Split an invoice between partners and store each share.

Money is handled as integer centavos (never floats), so shares always sum
exactly to the total. Remainders are distributed by largest-remainder.
"""
import sqlite3
from decimal import Decimal


def to_centavos(amount: str | Decimal | int) -> int:
    """Convert a BRL amount (e.g. "100.00") to centavos. Floats are rejected."""
    if isinstance(amount, float):
        raise TypeError("pass amounts as str/Decimal, not float")
    d = Decimal(amount)
    cents = d * 100
    if cents != cents.to_integral_value():
        raise ValueError(f"amount has sub-centavo precision: {amount}")
    return int(cents)


def split_centavos(total_centavos: int, weights: list[int]) -> list[int]:
    """Split total by integer weights; result sums exactly to total."""
    if total_centavos < 0 or not weights or any(w < 0 for w in weights):
        raise ValueError("invalid total or weights")
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("weights must not all be zero")
    shares = [total_centavos * w // weight_sum for w in weights]
    remainders = [total_centavos * w % weight_sum for w in weights]
    leftover = total_centavos - sum(shares)
    # Give the leftover centavos to the largest remainders (stable by index).
    for i in sorted(range(len(weights)), key=lambda i: -remainders[i])[:leftover]:
        shares[i] += 1
    return shares


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS invoice_shares (
               invoice_id TEXT NOT NULL,
               partner    TEXT NOT NULL,
               weight     INTEGER NOT NULL,
               amount_centavos INTEGER NOT NULL,
               PRIMARY KEY (invoice_id, partner)
           )"""
    )


def split_and_store(
    conn: sqlite3.Connection,
    invoice_id: str,
    total: str | Decimal | int,
    partners: dict[str, int],
) -> dict[str, int]:
    """Split `total` (BRL) among partners by weight and store each share.

    Returns {partner: centavos}. All rows are written in one transaction.
    """
    init_db(conn)
    names = list(partners)
    shares = split_centavos(to_centavos(total), [partners[n] for n in names])
    with conn:
        conn.executemany(
            "INSERT INTO invoice_shares VALUES (?, ?, ?, ?)",
            [(invoice_id, n, partners[n], s) for n, s in zip(names, shares)],
        )
    return dict(zip(names, shares))


def split_100_reais(conn: sqlite3.Connection, invoice_id: str) -> dict[str, int]:
    """R$ 100,00 split 50/30/20 between three partners."""
    return split_and_store(
        conn, invoice_id, "100.00", {"partner_a": 50, "partner_b": 30, "partner_c": 20}
    )


if __name__ == "__main__":
    c = sqlite3.connect(":memory:")
    print(split_100_reais(c, "INV-1"))  # {'partner_a': 5000, 'partner_b': 3000, 'partner_c': 2000}
