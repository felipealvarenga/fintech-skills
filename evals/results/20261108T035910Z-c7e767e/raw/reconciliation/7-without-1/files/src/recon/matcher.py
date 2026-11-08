from .models import Match, Result


def reconcile(bank, ledger, date_window_days=3):
    """Match bank lines to ledger lines.

    Pass 1: same non-empty reference. Equal amounts -> "reference";
            different amounts -> "amount_mismatch" (needs review).
    Pass 2: same amount, dates within window -> "fuzzy" (closest date first).
    Each transaction is used at most once.
    """
    free_ledger = list(ledger)
    free_bank = []
    matches = []

    for b in bank:
        cand = next(
            (l for l in free_ledger if b.reference and l.reference == b.reference),
            None,
        )
        if cand is None:
            free_bank.append(b)
            continue
        free_ledger.remove(cand)
        kind = "reference" if cand.amount == b.amount else "amount_mismatch"
        matches.append(Match(b, cand, kind, b.amount - cand.amount))

    still_unmatched = []
    for b in free_bank:
        cands = [
            l
            for l in free_ledger
            if l.amount == b.amount and abs((l.date - b.date).days) <= date_window_days
        ]
        if not cands:
            still_unmatched.append(b)
            continue
        best = min(cands, key=lambda l: abs((l.date - b.date).days))
        free_ledger.remove(best)
        matches.append(Match(b, best, "fuzzy", b.amount - best.amount))

    return Result(matches, still_unmatched, free_ledger)
