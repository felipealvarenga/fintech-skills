"""Push expense categorizations to Xero.

Xero is the source of truth once a customer edits a transaction there: if the
Xero transaction changed after our last sync, we skip it instead of overwriting.
"""
import logging

log = logging.getLogger(__name__)


def push(db, xero):
    for expense in db.query("SELECT * FROM expenses WHERE synced = false OR updated_at > last_synced_at"):
        if expense.last_synced_at is not None:
            remote = xero.get_bank_transaction(expense.xero_id)
            if remote["UpdatedDateUTC"] > expense.last_synced_at:
                log.warning("Skipping expense %s: changed in Xero since last sync", expense.id)
                db.execute(
                    "UPDATE expenses SET sync_conflict = true WHERE id = %s", (expense.id,)
                )
                continue
        xero.update_bank_transaction(expense.xero_id, {"LineItems": [{"AccountCode": expense.account_code}]})
        db.execute(
            "UPDATE expenses SET synced = true, sync_conflict = false, last_synced_at = now() WHERE id = %s",
            (expense.id,),
        )
