CREATE TABLE audit_events (
    event_id          uuid PRIMARY KEY,
    object_type       text NOT NULL,
    object_id         text NOT NULL,
    sequence          bigint NOT NULL,
    action            text NOT NULL,
    actor_type        text NOT NULL CHECK (actor_type IN ('user','service','agent','system')),
    actor_id          text NOT NULL,
    on_behalf_of      text,
    authorization_ref text,
    before            jsonb,
    after             jsonb,
    reason_code       text NOT NULL,
    reason_text       text,
    request_id        text NOT NULL,
    idempotency_key   text,
    occurred_at       timestamptz NOT NULL,
    recorded_at       timestamptz NOT NULL DEFAULT now(),
    source            text NOT NULL,
    prev_hash         text,
    event_hash        text NOT NULL,
    corrects_event_id uuid REFERENCES audit_events(event_id),
    UNIQUE (object_type, object_id, sequence)
);
CREATE INDEX audit_events_actor_time ON audit_events (actor_id, occurred_at);

-- Append only: the application role may insert and read, never change or delete.
-- (Replace app_role with the real role name.)
REVOKE ALL ON audit_events FROM app_role;
GRANT SELECT, INSERT ON audit_events TO app_role;
-- Retention: set per jurisdiction by compliance (commonly 5+ years); no purge job here.
