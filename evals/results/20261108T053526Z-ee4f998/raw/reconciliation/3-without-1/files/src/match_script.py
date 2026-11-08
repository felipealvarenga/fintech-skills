"""Current matcher: pairs lines by amount only."""
import csv


def load(path):
    return list(csv.DictReader(open(path)))


def match(ours, theirs):
    matched = []
    used = set()  # each of their lines may be matched only once
    for o in ours:
        for t in theirs:
            if t["id"] not in used and o["amount_minor"] == t["amount_minor"]:
                matched.append((o["id"], t["id"]))
                used.add(t["id"])
                break
    return matched


def remaining_difference(ours, theirs, matched):
    """Net unmatched amount (minor units): ours minus theirs."""
    our_ids = {o for o, _ in matched}
    their_ids = {t for _, t in matched}
    our_left = sum(int(o["amount_minor"]) for o in ours if o["id"] not in our_ids)
    their_left = sum(int(t["amount_minor"]) for t in theirs if t["id"] not in their_ids)
    return our_left - their_left


def month_end(ours, theirs, post_adjustment, period, max_auto=None):
    """Match, then auto-post one adjustment for any remaining difference.

    post_adjustment(period=..., amount_minor=..., memo=...) is supplied by the
    caller and does the actual ledger posting. If max_auto is set and the
    difference exceeds it (absolute, minor units), nothing is posted and the
    difference is returned for manual review.
    """
    matched = match(ours, theirs)
    diff = remaining_difference(ours, theirs, matched)
    posted = False
    if diff != 0 and (max_auto is None or abs(diff) <= max_auto):
        # Adjustment brings our side in line with theirs.
        post_adjustment(
            period=period,
            amount_minor=-diff,
            memo=f"Auto month-end adjustment {period}",
        )
        posted = True
    return {"matched": matched, "difference": diff, "posted": posted}
