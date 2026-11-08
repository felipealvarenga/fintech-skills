"""Where received webhook events are kept."""

class EventStore:
    def __init__(self, db):
        self.db = db

    def save(self, event_id: str, event_type: str, raw: bytes) -> None:
        self.db.execute("INSERT INTO webhook_events (id, type, raw, received_at) VALUES (%s, %s, %s, now())", (event_id, event_type, raw))
