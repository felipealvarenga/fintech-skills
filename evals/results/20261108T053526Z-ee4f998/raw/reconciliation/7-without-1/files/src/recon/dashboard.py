from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

from .loader import load_csv
from .matcher import reconcile
from .models import ReconciliationResult, Transaction

CSS = """
body{font-family:system-ui,sans-serif;margin:2rem;color:#1b1f24;background:#f6f8fa}
h1{margin-bottom:.25rem}.cards{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.card{background:#fff;border:1px solid #d0d7de;border-radius:8px;padding:1rem 1.25rem;min-width:150px}
.card b{display:block;font-size:1.5rem}.bad{color:#cf222e}.ok{color:#1a7f37}
table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:2rem}
th,td{border:1px solid #d0d7de;padding:.4rem .6rem;text-align:left;font-size:.9rem}
td.n{text-align:right;font-variant-numeric:tabular-nums}th{background:#eaeef2}
"""


def _txn_rows(txns: list[Transaction]) -> str:
    return "".join(
        f"<tr><td>{escape(t.id)}</td><td>{t.date}</td><td>{escape(t.reference)}</td>"
        f"<td>{escape(t.description)}</td><td class=n>{t.amount:,.2f}</td></tr>"
        for t in txns
    ) or "<tr><td colspan=5>None 🎉</td></tr>"


def _pair_rows(matches) -> str:
    return "".join(
        f"<tr><td>{escape(m.ledger.id)}</td><td>{escape(m.bank.id)}</td>"
        f"<td>{m.ledger.date}</td><td>{m.bank.date}</td><td>{escape(m.ledger.reference)}</td>"
        f"<td class=n>{m.ledger.amount:,.2f}</td><td class=n>{m.bank.amount:,.2f}</td>"
        f"<td class=n>{m.difference:,.2f}</td></tr>"
        for m in matches
    ) or "<tr><td colspan=8>None 🎉</td></tr>"


def render_html(r: ReconciliationResult) -> str:
    var_class = "ok" if r.variance == 0 else "bad"
    txn_head = "<tr><th>ID</th><th>Date</th><th>Reference</th><th>Description</th><th>Amount</th></tr>"
    pair_head = (
        "<tr><th>Ledger ID</th><th>Bank ID</th><th>Ledger date</th><th>Bank date</th>"
        "<th>Reference</th><th>Ledger amt</th><th>Bank amt</th><th>Diff</th></tr>"
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Reconciliation Dashboard</title><style>{CSS}</style></head><body>
<h1>Reconciliation Dashboard</h1>
<div class="cards">
<div class="card">Match rate<b>{r.match_rate:.1%}</b></div>
<div class="card">Matched<b>{len(r.matched)}</b></div>
<div class="card">Amount mismatches<b class="{'bad' if r.amount_mismatches else 'ok'}">{len(r.amount_mismatches)}</b></div>
<div class="card">Unmatched ledger<b class="{'bad' if r.unmatched_ledger else 'ok'}">{len(r.unmatched_ledger)}</b></div>
<div class="card">Unmatched bank<b class="{'bad' if r.unmatched_bank else 'ok'}">{len(r.unmatched_bank)}</b></div>
<div class="card">Net variance (ledger − bank)<b class="{var_class}">{r.variance:,.2f}</b></div>
</div>
<h2>Amount mismatches</h2><table>{pair_head}{_pair_rows(r.amount_mismatches)}</table>
<h2>Unmatched ledger entries</h2><table>{txn_head}{_txn_rows(r.unmatched_ledger)}</table>
<h2>Unmatched bank entries</h2><table>{txn_head}{_txn_rows(r.unmatched_bank)}</table>
<h2>Matched</h2><table>{pair_head}{_pair_rows(r.matched)}</table>
</body></html>"""


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Generate a ledger-vs-bank reconciliation dashboard.")
    p.add_argument("ledger", help="ledger CSV")
    p.add_argument("bank", help="bank statement CSV")
    p.add_argument("-o", "--output", default="reconciliation.html")
    p.add_argument("--tolerance", type=int, default=3, help="date tolerance in days (default 3)")
    args = p.parse_args(argv)

    result = reconcile(load_csv(args.ledger), load_csv(args.bank), args.tolerance)
    Path(args.output).write_text(render_html(result), encoding="utf-8")
    print(
        f"Wrote {args.output}: {len(result.matched)} matched, "
        f"{len(result.amount_mismatches)} mismatched, "
        f"{len(result.unmatched_ledger)} unmatched ledger, "
        f"{len(result.unmatched_bank)} unmatched bank, variance {result.variance:,.2f}"
    )


if __name__ == "__main__":
    main()
