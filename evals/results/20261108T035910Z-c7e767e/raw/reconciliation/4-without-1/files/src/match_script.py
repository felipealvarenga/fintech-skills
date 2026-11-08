"""Current matcher: pairs lines by amount within a 2% tolerance."""
import csv


def load(path):
    return list(csv.DictReader(open(path)))


TOLERANCE = 0.02  # 2% relative amount tolerance


def amounts_match(a, b, tolerance=TOLERANCE):
    a, b = int(a), int(b)
    return abs(a - b) <= tolerance * abs(a)


def match(ours, theirs):
    matched = []
    for o in ours:
        for t in theirs:
            if amounts_match(o["amount_minor"], t["amount_minor"]):
                matched.append((o["id"], t["id"]))
                break
    return matched
