"""Current matcher: pairs lines by amount only."""
import csv


def load(path):
    return list(csv.DictReader(open(path)))


def match(ours, theirs):
    matched = []
    for o in ours:
        for t in theirs:
            if o["amount_minor"] == t["amount_minor"]:
                matched.append((o["id"], t["id"]))
                break
    return matched


def remaining_difference(ours, theirs):
    """Net difference in minor units (ours - theirs).

    Matched pairs have equal amounts, so they cancel out and the total
    difference equals the net of the unmatched lines.
    """
    return (sum(int(o["amount_minor"]) for o in ours)
            - sum(int(t["amount_minor"]) for t in theirs))


def month_end(ours, theirs, period, post):
    """Match, then auto-post one adjustment for any remaining difference.

    `post` is a callable that writes the adjustment to the ledger; it receives
    a dict and is only called when the difference is non-zero. Returns
    (matched, adjustment), where adjustment is None if nothing was posted.
    """
    matched = match(ours, theirs)
    diff = remaining_difference(ours, theirs)
    if diff == 0:
        return matched, None
    adjustment = {
        "period": period,
        "amount_minor": -diff,  # offsets the difference
        "memo": f"Month-end auto adjustment {period}",
    }
    post(adjustment)
    return matched, adjustment
