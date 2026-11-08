import random
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from reconcile import Config, Line, reconcile  # noqa: E402


def L(src, id, d, amt, ref="", cur="BRL", kind=None):
    return Line(src, id, date.fromisoformat(d), amt, cur, ref,
                kind or ("payment" if src == "ledger" else "charge"), ())


def pairs(r):
    return sorted((tuple(m["ours"]), tuple(m["theirs"]), m["tier"]) for m in r["matches"])


class T(unittest.TestCase):
    def test_reference_beats_date(self):
        ours = [L("ledger", "p1", "2026-05-04", 100, "ch_b")]
        theirs = [L("stripe", "t1", "2026-05-04", 100, "ch_a"), L("stripe", "t2", "2026-05-09", 100, "ch_b")]
        r = reconcile(ours, theirs)
        self.assertEqual(pairs(r), [(("p1",), ("t2",), "1_reference")])

    def test_window(self):
        o = [L("ledger", "p1", "2026-05-04", 100)]
        self.assertEqual(len(reconcile(o, [L("stripe", "t", "2026-05-06", 100)])["matches"]), 1)
        self.assertEqual(len(reconcile(o, [L("stripe", "t", "2026-05-07", 100)])["matches"]), 0)

    def test_duplicates_one_to_one(self):
        o = [L("ledger", f"p{i}", "2026-05-04", 100) for i in (1, 2)]
        t = [L("stripe", f"t{i}", "2026-05-04", 100) for i in (1, 2)]
        r = reconcile(o, t)
        self.assertEqual(len(r["matches"]), 2)
        self.assertEqual(len({m["theirs"][0] for m in r["matches"]}), 2)

    def test_currency_mismatch(self):
        r = reconcile([L("ledger", "p", "2026-05-04", 100)], [L("stripe", "t", "2026-05-04", 100, cur="USD")])
        self.assertEqual(r["matches"], [])

    def _data(self):
        o = [L("ledger", "p1", "2026-05-04", 100, "a"), L("ledger", "p2", "2026-05-04", 100),
             L("ledger", "p3", "2026-05-05", 900)]
        t = [L("stripe", "t1", "2026-05-04", 100, "a"), L("stripe", "t2", "2026-05-05", 100),
             L("stripe", "t3", "2026-05-06", -20, kind="fee"),
             L("stripe", "t4", "2026-05-07", 7, kind="charge"),
             L("stripe", "po", "2026-05-10", -180, kind="payout")]
        return o, t

    def test_shuffled_same_result(self):
        o, t = self._data()
        base = reconcile(o, t)
        for seed in range(5):
            random.Random(seed).shuffle(o); random.Random(seed).shuffle(t)
            self.assertEqual(reconcile(o, t), base)

    def test_nothing_lost_or_doubled(self):
        o, t = self._data()
        r = reconcile(o, t)
        seen = [i for m in r["matches"] for i in m["ours"]] + [b["id"] for b in r["breaks"] if b["source"] == "ledger"]
        self.assertEqual(sorted(seen), sorted(l.id for l in o))
        # stripe ids: each appears once across matches (tier 1/2 charges + tier 3 group) or breaks,
        # except charges/fees that are both matched to ledger and listed in the payout group.
        t_ids = [i for m in r["matches"] if m["tier"] != "3_payout_net_of_fees" for i in m["theirs"]]
        self.assertEqual(len(t_ids), len(set(t_ids)))

    def test_fee_nets_payout(self):
        o, t = self._data()
        # charges matched: 100 + 100 ; unmatched charge t4 (7) is not netted -> payout needs 200-20=180
        r = reconcile(o, t)
        tier3 = [m for m in r["matches"] if m["tier"] == "3_payout_net_of_fees"]
        self.assertEqual(len(tier3), 1)
        self.assertEqual(set(tier3[0]["theirs"]), {"po", "t1", "t2", "t3"})
        self.assertIn(("t3", "fee"), [(b["id"], b["reason"]) for b in r["breaks"]])
        self.assertIn(("t4", "missing_ours"), [(b["id"], b["reason"]) for b in r["breaks"]])
        self.assertIn(("p3", "missing_theirs"), [(b["id"], b["reason"]) for b in r["breaks"]])


if __name__ == "__main__":
    unittest.main()
