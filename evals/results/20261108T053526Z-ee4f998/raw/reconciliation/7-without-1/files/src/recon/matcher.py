from __future__ import annotations

from .models import Match, ReconciliationResult, Transaction


def reconcile(
    ledger: list[Transaction],
    bank: list[Transaction],
    date_tolerance_days: int = 3,
) -> ReconciliationResult:
    """Match ledger entries to bank entries.

    Passes, in order (each bank row is used at most once):
      1. same reference and same amount            -> "exact"
      2. same amount, dates within tolerance        -> "fuzzy"
      3. same non-empty reference, different amount -> "amount_mismatch"
    Anything left over is reported as unmatched.
    """
    result = ReconciliationResult()
    remaining_ledger = sorted(ledger, key=lambda t: (t.date, t.id))
    remaining_bank = sorted(bank, key=lambda t: (t.date, t.id))

    def run_pass(predicate, kind, sink):
        nonlocal remaining_ledger, remaining_bank
        used_bank: set[int] = set()
        left: list[Transaction] = []
        for l in remaining_ledger:
            best = None
            best_gap = None
            for i, b in enumerate(remaining_bank):
                if i in used_bank or not predicate(l, b):
                    continue
                gap = abs((l.date - b.date).days)
                if best_gap is None or gap < best_gap:
                    best, best_gap = i, gap
            if best is None:
                left.append(l)
            else:
                used_bank.add(best)
                sink.append(Match(l, remaining_bank[best], kind))
        remaining_ledger = left
        remaining_bank = [b for i, b in enumerate(remaining_bank) if i not in used_bank]

    def within(l: Transaction, b: Transaction) -> bool:
        return abs((l.date - b.date).days) <= date_tolerance_days

    run_pass(
        lambda l, b: bool(l.reference) and l.reference == b.reference and l.amount == b.amount,
        "exact",
        result.matched,
    )
    run_pass(lambda l, b: l.amount == b.amount and within(l, b), "fuzzy", result.matched)
    run_pass(
        lambda l, b: bool(l.reference) and l.reference == b.reference,
        "amount_mismatch",
        result.amount_mismatches,
    )

    result.unmatched_ledger = remaining_ledger
    result.unmatched_bank = remaining_bank
    return result
