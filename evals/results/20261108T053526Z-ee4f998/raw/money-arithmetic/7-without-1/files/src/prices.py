"""Price input parsing for Brazilian ('1.234,56') and US ('1,234.56') formats."""

import re
from decimal import Decimal, InvalidOperation


def parse_price(text: str) -> Decimal:
    """Parse a user-typed price into a Decimal.

    Rules:
    - Currency symbols/letters and whitespace are ignored (e.g. 'R$ 1.234,56').
    - If both '.' and ',' appear, the last one is the decimal separator.
    - If one separator appears several times, it is a thousands separator.
    - If one separator appears once: exactly three digits after it (and a
      non-zero leading part) means thousands ('1.234' / '1,234' -> 1234);
      otherwise it is the decimal separator ('1,5', '12,34', '0,123').

    Raises ValueError on input that is not a valid price.
    """
    s = re.sub(r"[^\d.,+-]", "", text or "")
    sign = ""
    if s[:1] in "+-" and s[:1]:
        sign, s = ("-" if s[0] == "-" else ""), s[1:]
    if not s or not re.fullmatch(r"[\d.,]+", s) or not any(c.isdigit() for c in s):
        raise ValueError(f"invalid price: {text!r}")

    dot, comma = s.count("."), s.count(",")
    if dot and comma:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        if s.count(dec) > 1 or s.rfind(thou) > s.rfind(dec):
            raise ValueError(f"invalid price: {text!r}")
    elif dot or comma:
        sep = "." if dot else ","
        if s.count(sep) > 1:
            dec, thou = None, sep
        else:
            head, tail = s.split(sep)
            if len(tail) == 3 and head not in ("", "0"):
                dec, thou = None, sep
            else:
                dec, thou = sep, None
    else:
        dec = thou = None

    if thou:
        groups = s.split(dec)[0].split(thou) if dec else s.split(thou)
        if not groups[0] or any(len(g) != 3 for g in groups[1:]):
            raise ValueError(f"invalid price: {text!r}")
    normalized = s
    if thou:
        normalized = normalized.replace(thou, "")
    if dec:
        normalized = normalized.replace(dec, ".")
    try:
        return Decimal(sign + normalized)
    except InvalidOperation:
        raise ValueError(f"invalid price: {text!r}") from None
