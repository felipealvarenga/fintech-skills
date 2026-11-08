"""Price input parsing for Brazilian ('1.234,56') and US ('1,234.56') formats.

Returns integer minor units (money-arithmetic rules 1, 2, 8); never a float.
"""
import re
from decimal import Decimal

from money import exponent

_MAX_MINOR = 10**15  # business range guard


def parse_price(text: str, currency: str = "BRL") -> int:
    """Parse user-typed text into integer minor units of `currency`.

    Raises ValueError on ambiguous or malformed input, or on more decimals
    than the currency allows (no silent rounding).
    """
    exp = exponent(currency)
    s = text.strip().replace(" ", "")
    negative = s.startswith("-")
    if negative:
        s = s[1:]
    if not s or not re.fullmatch(r"[\d.,]+", s) or not s[0].isdigit() or not s[-1].isdigit():
        raise ValueError(f"invalid price: {text!r}")

    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec_sep = "." if last_dot > last_comma else ","
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        if s.count(sep) > 1:
            dec_sep = None  # repeated separator can only be grouping
        else:
            digits_after = len(s) - s.rfind(sep) - 1
            if digits_after == 3 and exp != 3:
                dec_sep = None  # 3 digits can't be decimals here: grouping
            elif digits_after == 3:
                raise ValueError(f"ambiguous price: {text!r}")
            else:
                dec_sep = sep
    else:
        dec_sep = None

    group_sep = {".": ",", ",": "."}[dec_sep] if dec_sep else (
        "." if "." in s else "," if "," in s else None)
    if dec_sep:
        int_part, _, frac = s.rpartition(dec_sep)
    else:
        int_part, frac = s, ""
    if dec_sep and dec_sep in int_part:
        raise ValueError(f"invalid price: {text!r}")
    if group_sep and group_sep in int_part:
        groups = int_part.split(group_sep)
        if not (1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:])):
            raise ValueError(f"invalid grouping: {text!r}")
        int_part = "".join(groups)
    if len(frac) > exp:
        raise ValueError(f"too many decimals for {currency}: {text!r}")

    minor = int(Decimal(f"{int_part}.{frac or '0'}").scaleb(exp))
    if minor >= _MAX_MINOR:
        raise ValueError(f"price out of range: {text!r}")
    return -minor if negative else minor
