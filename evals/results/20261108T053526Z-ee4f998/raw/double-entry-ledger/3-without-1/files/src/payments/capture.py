"""Model of a card capture and how its funds are split.

All amounts are integer minor units (cents) to avoid float rounding errors.
"""
from __future__ import annotations

from dataclasses import dataclass


def dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) // 100:,}.{abs(cents) % 100:02d}"


@dataclass(frozen=True)
class CardCapture:
    """A captured card payment.

    gross_cents:         amount charged to the cardholder
    processor_fee_cents: fee the processor deducts from settlement
    our_share_cents:     amount we keep (our platform take)

    The processor settles gross - processor_fee to us. We keep our_share and
    owe the remainder to the merchant, so the processor fee is borne by the
    merchant, not by us.
    """

    gross_cents: int
    processor_fee_cents: int
    our_share_cents: int

    def __post_init__(self) -> None:
        for name in ("gross_cents", "processor_fee_cents", "our_share_cents"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an int number of cents")
            if value < 0:
                raise ValueError(f"{name} must not be negative")
        if self.processor_fee_cents > self.gross_cents:
            raise ValueError("processor fee exceeds gross amount")
        if self.our_share_cents > self.settled_cents:
            raise ValueError("our share exceeds settled amount")

    @property
    def settled_cents(self) -> int:
        """Cash actually received from the processor."""
        return self.gross_cents - self.processor_fee_cents

    @property
    def merchant_payable_cents(self) -> int:
        """Amount we owe the merchant."""
        return self.settled_cents - self.our_share_cents

    def journal(self) -> list[tuple[str, int, int]]:
        """Double-entry lines as (account, debit_cents, credit_cents)."""
        return [
            ("cash_at_processor", self.settled_cents, 0),
            ("our_revenue", 0, self.our_share_cents),
            ("merchant_payable", 0, self.merchant_payable_cents),
        ]


def example() -> CardCapture:
    return CardCapture(gross_cents=10_000, processor_fee_cents=290, our_share_cents=500)


if __name__ == "__main__":
    c = example()
    print("Gross captured:   ", dollars(c.gross_cents))
    print("Processor fee:    ", dollars(c.processor_fee_cents))
    print("Settled to us:    ", dollars(c.settled_cents))
    print("We keep:          ", dollars(c.our_share_cents))
    print("Owed to merchant: ", dollars(c.merchant_payable_cents))
