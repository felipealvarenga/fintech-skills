"""Static HTML dashboard rendered from a stored run record (read-only)."""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

from .store import load_run


def _money(minor: int) -> str:
    return f"{minor / 100:,.2f}"


def render(rec: dict) -> str:
    m, c = rec["metrics"], rec["config"]
    cards = [
        ("Match rate (count)", f"{m['match_rate_count']:.1%}", m["match_rate_count"] >= c["min_match_rate_count"]),
        ("Match rate (amount)", f"{m['match_rate_amount']:.1%}", m["match_rate_amount"] >= c["min_match_rate_amount"]),
        ("Oldest open break", f"{m['oldest_break_days']} d", m["oldest_break_days"] <= c["max_oldest_break_days"]),
        ("Amount in unknown", _money(m["unknown_amount_minor"]), m["unknown_amount_minor"] <= c["max_unknown_minor"]),
    ]
    card_html = "".join(
        f'<div class="card {"ok" if ok else "bad"}"><h3>{escape(t)}</h3><p>{escape(v)}</p></div>'
        for t, v, ok in cards)
    reasons = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in m["breaks_by_reason"].items())
    breaks = "".join(
        f"<tr><td>{escape(b['side'])}</td><td>{escape(b['line_id'])}</td><td>{escape(b['reason'])}</td>"
        f"<td>{escape(b['owner'])}</td><td>{b['age_days']}</td>"
        f"<td>{_money(b['amount_minor'])} {escape(b['currency'])}</td><td>{escape(b['note'])}</td></tr>"
        for b in sorted(rec["breaks"], key=lambda b: -b["age_days"]))
    alerts = "".join(f"<li>{escape(a)}</li>" for a in rec["alerts"]) or "<li>None</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Reconciliation</title>
<style>body{{font-family:sans-serif;margin:2rem}}.card{{display:inline-block;padding:1rem;margin:.5rem;border-radius:8px;min-width:10rem}}
.ok{{background:#e6f6ea}}.bad{{background:#fde8e8}}table{{border-collapse:collapse;margin:1rem 0}}td,th{{border:1px solid #ccc;padding:.3rem .6rem}}</style></head>
<body><h1>Reconciliation run {escape(rec['run_at'])}</h1>
<p>As of {escape(str(c['as_of']))} · inputs ours {rec['input_hashes']['ours'][:12]} / theirs {rec['input_hashes']['theirs'][:12]}</p>
{card_html}<h2>Alerts</h2><ul>{alerts}</ul>
<h2>Breaks by reason</h2><table><tr><th>Reason</th><th>Count</th></tr>{reasons}</table>
<h2>Open breaks (oldest first)</h2><table><tr><th>Side</th><th>Line</th><th>Reason</th><th>Owner</th><th>Age (d)</th><th>Amount</th><th>Note</th></tr>{breaks}</table>
<h2>Matches</h2><p>{len(rec['matches'])} matches (tier 1: {sum(x['tier']==1 for x in rec['matches'])}, tier 2: {sum(x['tier']==2 for x in rec['matches'])}, tier 3: {sum(x['tier']==3 for x in rec['matches'])})</p>
</body></html>"""


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m recon.dashboard RUN.json OUT.html")
        return 2
    Path(argv[2]).write_text(render(load_run(Path(argv[1]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
