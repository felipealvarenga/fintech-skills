ALTER TABLE fees ADD COLUMN IF NOT EXISTS updated_by text;
ALTER TABLE fees ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS fee_audit_events (
    event_id     bigserial PRIMARY KEY,
    object_type  text        NOT NULL,
    object_id    text        NOT NULL,
    sequence     integer     NOT NULL,
    action       text        NOT NULL,
    actor_type   text        NOT NULL,
    actor_id     text        NOT NULL,
    on_behalf_of text,
    before       jsonb,
    after        jsonb,
    reason_code  text        NOT NULL,
    reason       text        NOT NULL DEFAULT '',
    request_id   text        NOT NULL,
    occurred_at  timestamptz NOT NULL,
    recorded_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (object_type, object_id, sequence)
);

-- Append only: the application role may insert and read, never update or delete.
-- Replace app_role with the real application role name.
REVOKE UPDATE, DELETE, TRUNCATE ON fee_audit_events FROM app_role;
GRANT SELECT, INSERT ON fee_audit_events TO app_role;
