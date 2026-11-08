"""Current matcher: pairs lines by amount only."""
import csv


def load(path):
    return list(csv.DictReader(open(path)))


def within_tolerance(a, b, tol=0.02):
    a, b = int(a), int(b)
    return abs(a - b) <= tol * abs(a)


def match(ours, theirs, tol=0.02):
    matched = []
    for o in ours:
        for t in theirs:
            if within_tolerance(o["amount_minor"], t["amount_minor"], tol):
                matched.append((o["id"], t["id"]))
                break
    return matched
