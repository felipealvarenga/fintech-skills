"""Holdout evaluation (unrun). Fails when precision of any auto-post class is below target.

Expects evals/holdout.jsonl: {"description","amount","label"} per line, labeled by an
accountant, versioned, and never used in prompts or rules. Set HOLDOUT_LLM to a
"module:factory" returning an object with .complete(prompt).
"""
import importlib
import json
import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import classify as c  # noqa: E402

HOLDOUT = os.path.join(os.path.dirname(__file__), "..", "evals", "holdout.jsonl")
TARGET_PRECISION = {"6100-software": 0.98, "6200-travel": 0.98, "6300-meals": 0.98}


@pytest.mark.skipif(not os.path.exists(HOLDOUT) or not os.environ.get("HOLDOUT_LLM"),
                    reason="holdout set or HOLDOUT_LLM not configured")
def test_precision_per_autopost_class():
    mod, fn = os.environ["HOLDOUT_LLM"].split(":")
    llm = getattr(importlib.import_module(mod), fn)()
    chart = c.load_chart(os.path.join(os.path.dirname(__file__), "..", "src", "chart.json"))
    rows = [json.loads(l) for l in open(HOLDOUT)]

    class Sink:
        def post(self, *a): pass

    posted, correct = Counter(), Counter()
    for i, r in enumerate(rows):
        rec = c.categorize_and_post(llm, Sink(), {"id": str(i), **{k: r[k] for k in ("description", "amount")}}, chart)
        if rec["status"] == "posted":
            posted[rec["category"]] += 1
            correct[rec["category"]] += rec["category"] == r["label"]
    for cat, target in TARGET_PRECISION.items():
        if posted[cat]:
            assert correct[cat] / posted[cat] >= target, f"{cat} precision below {target}"
    print("coverage", sum(posted.values()) / len(rows))
