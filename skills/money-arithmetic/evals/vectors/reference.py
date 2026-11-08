"""Reference implementation for the money-arithmetic vectors.

Amounts are integers in minor units with an ISO 4217 currency code. This module exists so the
vectors are known to be satisfiable; your own implementation is tested by pointing the
MONEY_SOLUTION environment variable at it.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext

EXPONENTS = {
    "USD": 2, "EUR": 2, "BRL": 2, "GBP": 2, "CAD": 2, "AUD": 2, "MXN": 2,
    "JPY": 0, "KRW": 0, "CLP": 0, "ISK": 0,
    "BHD": 3, "KWD": 3, "TND": 3, "JOD": 3, "OMR": 3,
}


class UnknownCurrency(ValueError):
    pass


class CurrencyMismatch(ValueError):
    pass


class InvalidAmount(ValueError):
    pass


def exponent(currency: str) -> int:
    try:
        return EXPONENTS[currency]
    except KeyError:
        raise UnknownCurrency(currency) from None


def to_minor(amount: str, currency: str) -> int:
    exp = exponent(currency)
    try:
        d = Decimal(amount)
    except InvalidOperation:
        raise InvalidAmount(amount) from None
    if not d.is_finite():
        raise InvalidAmount(amount)
    scaled = d.scaleb(exp)
    if scaled != scaled.to_integral_value():
        raise InvalidAmount(f"{amount} has more decimals than {currency} allows ({exp})")
    return int(scaled)


def from_minor(minor: int, currency: str) -> str:
    exp = exponent(currency)
    sign = "-" if minor < 0 else ""
    digits = str(abs(minor)).rjust(exp + 1, "0")
    if exp == 0:
        return sign + digits
    return f"{sign}{digits[:-exp]}.{digits[-exp:]}"


def add(a: tuple[int, str], b: tuple[int, str]) -> tuple[int, str]:
    if a[1] != b[1]:
        raise CurrencyMismatch(f"{a[1]} != {b[1]}")
    exponent(a[1])
    return (a[0] + b[0], a[1])


def allocate(amount: int, ratios: list[int]) -> list[int]:
    if not ratios or any(r < 0 for r in ratios):
        raise ValueError("ratios must be a non-empty list of non-negative integers")
    total = sum(ratios)
    if total == 0:
        raise ValueError("ratios must not all be zero")
    if amount < 0:
        return [-x for x in allocate(-amount, ratios)]
    shares = [amount * r // total for r in ratios]
    remainders = [(amount * r) % total for r in ratios]
    leftover = amount - sum(shares)
    order = sorted(range(len(ratios)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        shares[i] += 1
    return shares


def apply_rate(amount: int, rate: str, rounding: str = ROUND_HALF_EVEN) -> int:
    with localcontext() as ctx:
        ctx.prec = 34
        return int((Decimal(amount) * Decimal(rate)).quantize(Decimal(1), rounding=rounding))


def convert(amount: int, from_currency: str, to_currency: str, rate: str,
            rounding: str = ROUND_HALF_EVEN) -> int:
    exp_from = exponent(from_currency)
    exp_to = exponent(to_currency)
    with localcontext() as ctx:
        ctx.prec = 34
        major = Decimal(amount).scaleb(-exp_from)
        target = (major * Decimal(rate)).scaleb(exp_to)
        return int(target.quantize(Decimal(1), rounding=rounding))
