"""Static HTML dashboard rendered from stored run records. Read-only."""
from __future__ import annotations

from html import escape


def _money(minor: int) -> str:
    # Display only; assumes 2 decimals. Currency is shown alongside in the tables.
    return f"{minor / 100:,.2f}"


def _status(ok: bool) -> str:
    return "ok" if ok else "bad"


def render(records: list[dict]) -> str:
    if not records:
        return "<html><body><h1>Reconciliation</h1><p>No runs yet.</p></body></html>"
    latest = records[-1]
    m, p = latest["metrics"], latest["parameters"]
    cards = [
        ("Match rate (count)", f"{m['match_rate_count']:.1%}", m["match_rate_count"] >= p["min_match_rate_count"]),
        ("Match rate (amount)", f"{m['match_rate_amount']:.1%}", m["match_rate_amount"] >= p["min_match_rate_amount"]),
        ("Oldest open break", f"{m['oldest_open_break_days']} d", m["oldest_open_break_days"] <= p["max_oldest_break_days"]),
        ("Amount in unknown", _money(m["unknown_amount_minor"]), m["unknown_amount_minor"] <= p["max_unknown_amount_minor"]),
    ]
    card_html = "".join(
        f'<div class="card {_status(ok)}"><div class="v">{escape(v)}</div><div>{escape(k)}</div></div>'
        for k, v, ok in cards)
    reasons = "".join(f"<tr><td>{escape(r)}</td><td>{n}</td></tr>" for r, n in m["breaks_by_reason"].items())
    breaks = "".join(
        f"<tr><td>{escape(b['line_id'])}</td><td>{b['side']}</td><td>{escape(b['reason'])}</td>"
        f"<td>{escape(b['owner'])}</td><td>{b['age_days']}</td>"
        f"<td>{_money(b['amount_minor'])} {escape(b['currency'])}</td><td>{escape(b['detail'])}</td></tr>"
        for b in sorted(latest["breaks"], key=lambda b: -b["age_days"]))
    alerts = "".join(f"<li>{escape(a)}</li>" for a in latest["alerts"]) or "<li>none</li>"
    history = "".join(
        f"<tr><td>{escape(r['run_at'])}</td><td>{r['metrics']['match_rate_count']:.1%}</td>"
        f"<td>{len(r['breaks'])}</td><td>{r['metrics']['oldest_open_break_days']}</td></tr>"
        for r in reversed(records))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Reconciliation</title>
<style>body{{font:14px sans-serif;margin:2em}}.cards{{display:flex;gap:1em}}
.card{{padding:1em;border-radius:6px;min-width:10em}}.v{{font-size:1.8em}}
.ok{{background:#e6f4ea}}.bad{{background:#fce8e6}}
table{{border-collapse:collapse;margin:1em 0}}td,th{{border:1px solid #ccc;padding:4px 8px}}</style></head>
<body><h1>Reconciliation</h1><p>Latest run {escape(latest['run_at'])}, as of {escape(p['as_of'])}.
Inputs: ours {latest['inputs']['ours_sha256'][:12]}, theirs {latest['inputs']['theirs_sha256'][:12]}</p>
<div class="cards">{card_html}</div>
<h2>Alerts</h2><ul>{alerts}</ul>
<h2>Breaks by reason</h2><table>{reasons}</table>
<h2>Open breaks</h2><table><tr><th>Line</th><th>Side</th><th>Reason</th><th>Owner</th><th>Age (d)</th><th>Amount</th><th>Detail</th></tr>{breaks}</table>
<h2>Run history</h2><table><tr><th>Run</th><th>Match rate</th><th>Breaks</th><th>Oldest (d)</th></tr>{history}</table>
</body></html>"""
