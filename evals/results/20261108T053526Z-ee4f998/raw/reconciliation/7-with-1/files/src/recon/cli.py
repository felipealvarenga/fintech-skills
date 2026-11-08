"""Daily job: python -m recon.cli --ledger L.csv --processor P.csv --as-of 2026-11-08 --runs runs/ --html dashboard.html

Run over the whole open window each day. The wall clock is read here, at the edge,
only to stamp the run record; reconcile() itself never sees it.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from . import adapters, dashboard, store
from .models import Config
from .reconcile import reconcile


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--processor", type=Path, required=True)
    ap.add_argument("--as-of", type=date.fromisoformat, default=None)
    ap.add_argument("--window", type=int, default=2, help="tier 2 window, business days")
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--html", type=Path, default=Path("dashboard.html"))
    a = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    cfg = Config(as_of=a.as_of or now.date(), window_business_days=a.window)
    ours, theirs = adapters.load_ledger(a.ledger), adapters.load_processor(a.processor)
    result = reconcile(ours, theirs, cfg)
    path = store.write_record(a.runs, store.build_record(ours, theirs, cfg, result, now))
    a.html.write_text(dashboard.render(store.load_records(a.runs)), encoding="utf-8")

    print(f"run record: {path}\ndashboard: {a.html}")
    for alert in result.alerts:
        print("ALERT:", alert)
    return 1 if any(x.startswith("PAGE") for x in result.alerts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
