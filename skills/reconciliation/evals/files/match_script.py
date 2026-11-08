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
