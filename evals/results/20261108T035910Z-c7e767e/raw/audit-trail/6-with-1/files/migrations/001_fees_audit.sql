-- Traceability columns on fees (latest change only; full history is in audit_events).
ALTER TABLE fees
  ADD COLUMN updated_by text,
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE audit_events (
  event_id     uuid PRIMARY KEY,
  object_type  text        NOT NULL,
  object_id    text        NOT NULL,
  sequence     bigint      NOT NULL,
  action       text        NOT NULL,
  actor_type   text        NOT NULL CHECK (actor_type IN ('user','service','agent','system')),
  actor_id     text        NOT NULL,
  on_behalf_of text,
  before       jsonb,
  after        jsonb,
  reason_code  text        NOT NULL,
  reason_text  text,
  request_id   text        NOT NULL,
  occurred_at  timestamptz NOT NULL,
  recorded_at  timestamptz NOT NULL DEFAULT now(),
  source       text        NOT NULL,
  UNIQUE (object_type, object_id, sequence)
);

-- Append only for the application role (replace app_rw with your role name).
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM app_rw;
GRANT INSERT, SELECT ON audit_events TO app_rw;
