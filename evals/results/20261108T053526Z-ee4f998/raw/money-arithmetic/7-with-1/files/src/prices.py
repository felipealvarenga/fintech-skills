"""Price input parsing for user-typed text.

Returns integer minor units (never a float). Accepts Brazilian ('1.234,56')
and US ('1,234.56') styles.

Separator rules:
  * both '.' and ',' present: the last one is the decimal separator.
  * one kind, appearing more than once: thousands separator ('1.234.567').
  * one kind, appearing once: decimal separator, except when exactly three
    digits follow it, which reads as thousands ('1.234' -> 1234). For a
    3-decimal currency that case is truly ambiguous and is refused.
"""
import re

from money import exponent, to_minor

_ALLOWED = re.compile(r"^-?[\d.,]+$")


def _to_canonical(text: str, currency: str) -> str:
    s = text.strip().replace(" ", "")
    if not _ALLOWED.match(s):
        raise ValueError(f"invalid price: {text!r}")
    sign = "-" if s.startswith("-") else ""
    s = s.lstrip("-")

    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        if s.count(dec) > 1 or s.rfind(thou) > s.rfind(dec):
            raise ValueError(f"invalid price: {text!r}")
    else:
        sep = "." if "." in s else "," if "," in s else None
        if sep is None:
            dec, thou = None, None
        elif s.count(sep) > 1:
            dec, thou = None, sep
        elif len(s) - s.index(sep) - 1 == 3:
            if exponent(currency) == 3:
                raise ValueError(f"ambiguous price: {text!r}")
            dec, thou = None, sep
        else:
            dec, thou = sep, ("," if sep == "." else ".")

    if thou:
        groups = s.split(dec)[0].split(thou)
        if not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])):
            raise ValueError(f"invalid thousands grouping: {text!r}")
        s = s.replace(thou, "")
    if dec:
        s = s.replace(dec, ".")
    if not s or s.startswith(".") or s.endswith("."):
        raise ValueError(f"invalid price: {text!r}")
    return sign + s


def parse_price(text: str, currency: str = "BRL") -> int:
    """Parse user-typed price into integer minor units of `currency`."""
    return to_minor(_to_canonical(text, currency), currency)
