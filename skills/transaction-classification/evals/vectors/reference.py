"""Reference implementation for the transaction-classification vectors.

The deterministic layers around a classifier: merchant normalization, transfer pairing,
structured-output validation against the chart, and the auto-post gate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


def normalize_merchant(description: str) -> str:
    """Deterministic key for 'same merchant': upper case, store and reference numbers removed,
    URLs removed, separators collapsed. It is not a display name."""
    s = description.upper().replace("*", " ")
    tokens = []
    for tok in re.split(r"\s+", s.strip()):
        if not tok:
            continue
        if "." in tok and re.search(r"[A-Z]", tok):  # a domain such as HELP.UBER.COM
            continue
        if tok.startswith("#"):
            continue
        if re.search(r"\d", tok):  # store numbers, card suffixes, reference codes
            continue
        tokens.append(tok.strip(".,;:-"))
    return " ".join(t for t in tokens if t)


@dataclass(frozen=True)
class Line:
    id: str
    account: str
    date: date
    amount: int  # signed minor units: negative is money out
    description: str = ""


def pair_transfers(lines: list[Line], window_days: int = 3) -> tuple[list[tuple[str, str]], list[Line]]:
    """Match a debit in one account with a credit of the same amount in another account within
    the window. One-to-one, deterministic, earliest first."""
    ordered = sorted(lines, key=lambda l: (l.date, l.id))
    used: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for out in ordered:
        if out.amount >= 0 or out.id in used:
            continue
        for inc in ordered:
            if inc.id in used or inc.amount != -out.amount or inc.account == out.account:
                continue
            if abs((inc.date - out.date).days) <= window_days:
                used.update({out.id, inc.id})
                pairs.append((out.id, inc.id))
                break
    remaining = [l for l in ordered if l.id not in used]
    return pairs, remaining


class InvalidOutput(ValueError):
    pass


def validate_output(obj: dict, chart: set[str]) -> dict:
    """The model's answer must name a category id from the chart, a confidence in [0, 1] and a
    rationale. Anything else is invalid; the caller routes it to review as uncategorized."""
    if not isinstance(obj, dict):
        raise InvalidOutput("not an object")
    cat = obj.get("category_id")
    conf = obj.get("confidence")
    rationale = obj.get("rationale")
    if not isinstance(cat, str) or cat not in chart:
        raise InvalidOutput(f"category {cat!r} is not in the chart")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= float(conf) <= 1:
        raise InvalidOutput("confidence must be a number in [0, 1]")
    if not isinstance(rationale, str) or not rationale.strip():
        raise InvalidOutput("rationale is required")
    return {"category_id": cat, "confidence": float(conf), "rationale": rationale.strip()}


@dataclass
class GatePolicy:
    default_threshold: float = 0.9
    thresholds: dict[str, float] = field(default_factory=dict)
    never_auto: set[str] = field(default_factory=set)
    max_auto_amount: int = 250_000  # minor units

    def threshold(self, category_id: str) -> float:
        return self.thresholds.get(category_id, self.default_threshold)


def decide(output: dict | None, amount_abs: int, policy: GatePolicy, *, is_split: bool = False,
           is_transfer: bool = False) -> tuple[str, str]:
    """Returns (action, category): action is 'auto' or 'review'."""
    if output is None:
        return ("review", "uncategorized")
    cat = output["category_id"]
    if is_split or is_transfer or cat in policy.never_auto:
        return ("review", cat)
    if amount_abs > policy.max_auto_amount:
        return ("review", cat)
    if output["confidence"] >= policy.threshold(cat):
        return ("auto", cat)
    return ("review", cat)


def classify_with_layers(description: str, rules: dict[str, str], approved: dict[str, str],
                         model_output: dict | None, chart: set[str]) -> tuple[str, dict | None]:
    """Rule, then approved repeat, then the model. Returns (layer, validated output or None)."""
    key = normalize_merchant(description)
    if key in rules:
        return ("rule", {"category_id": rules[key], "confidence": 1.0, "rationale": "user rule"})
    if key in approved:
        return ("approved_repeat", {"category_id": approved[key], "confidence": 1.0, "rationale": "approved before"})
    if model_output is None:
        return ("model", None)
    try:
        return ("model", validate_output(model_output, chart))
    except InvalidOutput:
        return ("model", None)
