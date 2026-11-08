"""Invoice splitting in integer centavos (no floats), so shares always sum to the total."""
from decimal import Decimal

# In-memory store: invoice_id -> {partner: share in centavos}.
# Replace with a real persistence layer (DB) when one exists.
SHARES: dict[str, dict[str, int]] = {}


def to_centavos(amount: str | Decimal) -> int:
    """Convert a BRL amount like '100.00' to centavos. Floats are rejected on purpose."""
    if isinstance(amount, float):
        raise TypeError("pass amounts as str or Decimal, not float")
    return int((Decimal(amount) * 100).to_integral_exact())


def format_brl(centavos: int) -> str:
    reais, cents = divmod(centavos, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{cents:02d}"


def split_centavos(total: int, weights: list[int]) -> list[int]:
    """Split `total` centavos proportionally to integer `weights` (largest remainder).

    The result always sums exactly to `total`.
    """
    weight_sum = sum(weights)
    base = [total * w // weight_sum for w in weights]
    leftover = total - sum(base)
    # Hand remaining centavos to the largest fractional remainders (ties: earlier partner).
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % weight_sum), i))
    for i in order[:leftover]:
        base[i] += 1
    return base


def split_and_store_invoice(
    invoice_id: str,
    total_centavos: int = 10_000,  # R$ 100,00
    partners: dict[str, int] | None = None,
) -> dict[str, int]:
    """Split an invoice between partners (default 50/30/20) and store each share."""
    partners = partners or {"partner_a": 50, "partner_b": 30, "partner_c": 20}
    shares = dict(zip(partners, split_centavos(total_centavos, list(partners.values()))))
    assert sum(shares.values()) == total_centavos
    SHARES[invoice_id] = shares
    return shares


if __name__ == "__main__":
    print({k: format_brl(v) for k, v in split_and_store_invoice("INV-1").items()})
    # Uneven case that breaks the float version: R$ 100,00 in thirds.
    print(split_centavos(10_000, [1, 1, 1]))  # [3334, 3333, 3333] -> sums to 10000
