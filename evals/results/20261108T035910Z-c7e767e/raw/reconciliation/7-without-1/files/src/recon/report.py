from datetime import date
from decimal import Decimal
from html import escape


def summarize(result):
    ub = sum((t.amount for t in result.unmatched_bank), Decimal(0))
    ul = sum((t.amount for t in result.unmatched_ledger), Decimal(0))
    mismatch = sum((m.difference for m in result.matches), Decimal(0))
    total = len(result.matches) + len(result.unmatched_bank) + len(result.unmatched_ledger)
    return {
        "matched": len(result.matches),
        "needs_review": sum(1 for m in result.matches if m.kind != "reference"),
        "unmatched_bank": len(result.unmatched_bank),
        "unmatched_ledger": len(result.unmatched_ledger),
        "unmatched_bank_amount": ub,
        "unmatched_ledger_amount": ul,
        "matched_difference": mismatch,
        "net_variance": ub - ul + mismatch,
        "match_rate": (len(result.matches) / total * 100) if total else 100.0,
    }


def _txn_rows(txns):
    return "".join(
        f"<tr><td>{escape(t.id)}</td><td>{t.date}</td><td>{escape(t.reference)}</td>"
        f"<td>{escape(t.description)}</td><td class=n>{t.amount:,.2f}</td></tr>"
        for t in txns
    ) or "<tr><td colspan=5>None 🎉</td></tr>"


def render_html(result):
    s = summarize(result)
    match_rows = "".join(
        f"<tr class={m.kind}><td>{escape(m.bank.id)}</td><td>{escape(m.ledger.id)}</td>"
        f"<td>{escape(m.bank.reference)}</td><td>{m.bank.date}</td><td>{m.ledger.date}</td>"
        f"<td class=n>{m.bank.amount:,.2f}</td><td class=n>{m.ledger.amount:,.2f}</td>"
        f"<td class=n>{m.difference:,.2f}</td><td>{m.kind.replace('_', ' ')}</td></tr>"
        for m in result.matches
    ) or "<tr><td colspan=9>None</td></tr>"
    head = "<tr><th>ID</th><th>Date</th><th>Reference</th><th>Description</th><th>Amount</th></tr>"
    cards = [
        ("Match rate", f"{s['match_rate']:.1f}%"),
        ("Matched", s["matched"]),
        ("Needs review", s["needs_review"]),
        ("Unmatched bank", f"{s['unmatched_bank']} ({s['unmatched_bank_amount']:,.2f})"),
        ("Unmatched ledger", f"{s['unmatched_ledger']} ({s['unmatched_ledger_amount']:,.2f})"),
        ("Net variance", f"{s['net_variance']:,.2f}"),
    ]
    cards_html = "".join(f"<div class=card><h3>{k}</h3><p>{v}</p></div>" for k, v in cards)
    return f"""<!doctype html><html><head><meta charset=utf-8>
<title>Reconciliation Dashboard</title><style>
body{{font-family:system-ui,sans-serif;margin:2rem;color:#222}}
.cards{{display:flex;gap:1rem;flex-wrap:wrap}}
.card{{border:1px solid #ddd;border-radius:8px;padding:.5rem 1rem;min-width:140px}}
.card h3{{margin:0;font-size:.8rem;color:#666}}.card p{{margin:.2rem 0;font-size:1.3rem;font-weight:600}}
table{{border-collapse:collapse;width:100%;margin-bottom:2rem}}
th,td{{border-bottom:1px solid #eee;padding:.3rem .6rem;text-align:left}}.n{{text-align:right}}
tr.amount_mismatch{{background:#fde8e8}}tr.fuzzy{{background:#fff7e0}}
</style></head><body>
<h1>Reconciliation Dashboard</h1><p>Generated {date.today()}</p>
<div class=cards>{cards_html}</div>
<h2>Matches</h2><table><tr><th>Bank ID</th><th>Ledger ID</th><th>Reference</th><th>Bank date</th>
<th>Ledger date</th><th>Bank amt</th><th>Ledger amt</th><th>Diff</th><th>Type</th></tr>{match_rows}</table>
<h2>Unmatched bank transactions</h2><table>{head}{_txn_rows(result.unmatched_bank)}</table>
<h2>Unmatched ledger entries</h2><table>{head}{_txn_rows(result.unmatched_ledger)}</table>
</body></html>"""
