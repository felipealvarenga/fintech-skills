import random
import unittest

from reconcile import Config, reconcile, _line

CFG = Config(window_days=2, as_of="2026-05-20")


def L(src, id_, d, amt, ref="", cur="BRL", desc="charge"):
    return _line(src, id_, d, amt, cur, ref, desc if src == "stripe" else "payment", {})


def tiers(r):
    return {(m["ours"], m["theirs"]): m["tier"] for m in r["matches"]}


class T(unittest.TestCase):
    def test_reference_beats_date(self):
        o = [L("ledger", "p1", "2026-05-04", 100, "ch_1")]
        t = [L("stripe", "t1", "2026-05-04", 100), L("stripe", "t2", "2026-05-06", 100, "ch_1")]
        self.assertEqual(tiers(reconcile(o, t, CFG)), {("p1", "t2"): 1})

    def test_window_edges(self):
        o = [L("ledger", "p1", "2026-05-04", 100)]
        self.assertEqual(len(reconcile(o, [L("stripe", "t1", "2026-05-06", 100)], CFG)["matches"]), 1)
        self.assertEqual(len(reconcile(o, [L("stripe", "t1", "2026-05-07", 100)], CFG)["matches"]), 0)

    def test_duplicates_one_to_one(self):
        o = [L("ledger", "p1", "2026-05-04", 100), L("ledger", "p2", "2026-05-04", 100)]
        t = [L("stripe", "t1", "2026-05-04", 100), L("stripe", "t2", "2026-05-04", 100)]
        r = reconcile(o, t, CFG)
        self.assertEqual(len(r["matches"]), 2)
        self.assertEqual(len({m["theirs"] for m in r["matches"]}), 2)

    def test_currency_mismatch(self):
        r = reconcile([L("ledger", "p1", "2026-05-04", 100)],
                      [L("stripe", "t1", "2026-05-04", 100, cur="USD")], CFG)
        self.assertEqual(r["matches"], [])

    def test_conflicting_references_do_not_date_match(self):
        r = reconcile([L("ledger", "p1", "2026-05-04", 100, "a")],
                      [L("stripe", "t1", "2026-05-04", 100, "b")], CFG)
        self.assertEqual(r["matches"], [])

    def test_shuffle_invariant(self):
        o = [L("ledger", f"p{i}", "2026-05-04", 100) for i in range(5)]
        t = [L("stripe", f"t{i}", "2026-05-04", 100) for i in range(5)]
        base = reconcile(o, t, CFG)
        random.seed(1)
        random.shuffle(o); random.shuffle(t)
        self.assertEqual(reconcile(o, t, CFG), base)

    def test_nothing_lost_or_doubled(self):
        o = [L("ledger", "p1", "2026-05-04", 100), L("ledger", "p2", "2026-05-04", 7)]
        t = [L("stripe", "t1", "2026-05-04", 100), L("stripe", "t2", "2026-05-04", 9)]
        r = reconcile(o, t, CFG)
        ids = [m["ours"] for m in r["matches"]] + [m["theirs"] for m in r["matches"]] \
            + [b["id"] for b in r["breaks"]]
        self.assertEqual(sorted(ids), ["p1", "p2", "t1", "t2"])

    def test_payout_nets_fees(self):
        t = [L("stripe", "c1", "2026-05-04", 1000), L("stripe", "f1", "2026-05-05", -100, desc="fee"),
             L("stripe", "po", "2026-05-10", -900, desc="payout")]
        r = reconcile([], t, CFG)
        self.assertEqual(r["groups"][0]["rule"], "payout_nets_charges_and_fees")
        self.assertFalse([b for b in r["breaks"] if b["id"] == "po"])
        self.assertIn("f1", [b["id"] for b in r["breaks"] if b["reason"] == "fee"])

    def test_payout_mismatch_is_unknown(self):
        t = [L("stripe", "c1", "2026-05-04", 1000), L("stripe", "po", "2026-05-10", -900, desc="payout")]
        r = reconcile([], t, CFG)
        self.assertTrue(any(b["id"] == "po" and b["reason"] == "unknown" and b["pages_person"]
                            for b in r["breaks"]))


if __name__ == "__main__":
    unittest.main()
