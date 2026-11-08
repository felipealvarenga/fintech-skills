import argparse

from .loader import load_csv
from .matcher import reconcile
from .report import render_html, summarize


def main(argv=None):
    p = argparse.ArgumentParser(prog="recon", description="Bank vs ledger reconciliation dashboard")
    p.add_argument("bank_csv")
    p.add_argument("ledger_csv")
    p.add_argument("-o", "--output", default="dashboard.html")
    p.add_argument("--window", type=int, default=3, help="date tolerance (days) for fuzzy matches")
    a = p.parse_args(argv)

    result = reconcile(load_csv(a.bank_csv), load_csv(a.ledger_csv), a.window)
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(render_html(result))
    s = summarize(result)
    print(f"Wrote {a.output}: {s['matched']} matched, {s['needs_review']} need review, "
          f"{s['unmatched_bank']} bank / {s['unmatched_ledger']} ledger unmatched")


if __name__ == "__main__":
    main()
