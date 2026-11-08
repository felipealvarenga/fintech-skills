"""Nightly push of journal entries to QuickBooks Online."""
def push(qbo, entries):
    for e in qbo.list_journal_entries(since=entries[0]["date"]):
        qbo.delete_journal_entry(e["Id"])
    for e in entries:
        qbo.create_journal_entry(e)
