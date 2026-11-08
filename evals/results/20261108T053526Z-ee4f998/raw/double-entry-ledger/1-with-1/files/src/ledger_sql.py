"""Postgres-style (psycopg, %s placeholders) Store for ledger.Ledger.

Runs inside the caller's transaction so entry and balance-cache update commit together.
"""
from datetime import date

from ledger import Entry, Posting


class SqlStore:
    def __init__(self, db):
        self.db = db

    def get_by_ref(self, ref):
        row = self.db.execute(
            "SELECT id, effective_date, recorded_at, reverses_ref, description "
            "FROM journal_entries WHERE external_ref = %s", (ref,)).fetchone()
        if not row:
            return None
        rows = self.db.execute(
            "SELECT account, side, amount_minor, currency FROM postings WHERE entry_id = %s "
            "ORDER BY id", (row[0],)).fetchall()
        return Entry(ref, row[1], tuple(Posting(*r) for r in rows), row[2], row[3], row[4])

    def closed_through(self):
        row = self.db.execute("SELECT closed_through FROM ledger_state").fetchone()
        return row[0] if row else None

    def append(self, e: Entry):
        entry_id = self.db.execute(
            "INSERT INTO journal_entries (external_ref, effective_date, recorded_at, "
            "reverses_ref, description) VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (e.external_ref, e.effective_date, e.recorded_at, e.reverses, e.description),
        ).fetchone()[0]
        for p in e.postings:
            self.db.execute(
                "INSERT INTO postings (entry_id, account, side, amount_minor, currency) "
                "VALUES (%s,%s,%s,%s,%s)",
                (entry_id, p.account, p.side, p.amount_minor, p.currency))

    def sums(self, account, currency, as_of: date | None):
        row = self.db.execute(
            "SELECT COALESCE(SUM(p.amount_minor) FILTER (WHERE p.side='debit'),0), "
            "COALESCE(SUM(p.amount_minor) FILTER (WHERE p.side='credit'),0) "
            "FROM postings p JOIN journal_entries e ON e.id = p.entry_id "
            "WHERE p.account = %s AND p.currency = %s AND (%s IS NULL OR e.effective_date <= %s)",
            (account, currency, as_of, as_of)).fetchone()
        return int(row[0]), int(row[1])
