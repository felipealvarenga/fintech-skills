CREATE TABLE audit_events (
    event_id        uuid PRIMARY KEY,
    object_type     text        NOT NULL,
    object_id       text        NOT NULL,
    sequence        bigint      NOT NULL,
    action          text        NOT NULL,
    actor_type      text        NOT NULL CHECK (actor_type IN ('user','service','agent','system')),
    actor_id        text        NOT NULL,
    on_behalf_of    text,
    before          jsonb       NOT NULL,
    after           jsonb       NOT NULL,
    reason_code     text        NOT NULL,
    reason_text     text        NOT NULL DEFAULT '',
    request_id      text        NOT NULL,
    idempotency_key text,
    occurred_at     timestamptz NOT NULL,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    source          text        NOT NULL,
    prev_hash       text        NOT NULL,
    event_hash      text        NOT NULL,
    UNIQUE (object_type, object_id, sequence)
);

CREATE INDEX audit_events_actor_time ON audit_events (actor_id, occurred_at);
CREATE INDEX audit_events_object_time ON audit_events (object_type, object_id, occurred_at);

-- Append-only: the application role may only insert and read.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM app_role;
GRANT INSERT, SELECT ON audit_events TO app_role;

CREATE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
