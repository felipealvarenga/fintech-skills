"""Price input parsing for Brazilian ('1.234,56') and US ('1,234.56') formats."""

import re
from decimal import Decimal, InvalidOperation

_VALID = re.compile(r"^-?[\d.,]+$")


def parse_price(text: str) -> Decimal:
    """Parse a user-typed price into a Decimal.

    Rules:
    - Both '.' and ',' present: the last one is the decimal separator.
    - One kind of separator, appearing several times: thousands separator.
    - One separator appearing once: thousands separator if followed by exactly
      3 digits (e.g. '1,234' / '1.234' -> 1234), otherwise decimal separator
      (e.g. '12,5' -> 12.5). Inputs like '1,234' are inherently ambiguous.

    Raises ValueError on malformed input.
    """
    s = text.strip().replace(" ", "").replace("R$", "").replace("$", "")
    if not s or not _VALID.match(s):
        raise ValueError(f"Invalid price: {text!r}")

    sign = ""
    if s.startswith("-"):
        sign, s = "-", s[1:]

    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec_idx = max(last_dot, last_comma)
        dec_char = s[dec_idx]
        thou_char = "," if dec_char == "." else "."
        if s.count(dec_char) > 1:
            raise ValueError(f"Invalid price: {text!r}")
        int_part, frac_part = s[:dec_idx], s[dec_idx + 1:]
        groups = int_part.split(thou_char)
    else:
        sep = "." if last_dot >= 0 else "," if last_comma >= 0 else None
        if sep is None:
            int_part, frac_part, groups = s, "", [s]
        elif s.count(sep) > 1 or len(s) - s.rfind(sep) - 1 == 3:
            # thousands separator only
            groups, frac_part = s.split(sep), ""
        else:
            int_part, frac_part = s.split(sep)
            groups = [int_part]

    # Validate thousands grouping (first group 1-3 digits, rest exactly 3).
    if len(groups) > 1 and not (
        0 < len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])
    ):
        raise ValueError(f"Invalid price: {text!r}")
    digits = "".join(groups)
    if not digits.isdigit() or (frac_part and not frac_part.isdigit()):
        raise ValueError(f"Invalid price: {text!r}")

    try:
        return Decimal(f"{sign}{digits}.{frac_part or '0'}")
    except InvalidOperation:
        raise ValueError(f"Invalid price: {text!r}")
