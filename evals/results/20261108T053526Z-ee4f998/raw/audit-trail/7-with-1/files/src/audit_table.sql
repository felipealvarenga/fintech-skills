-- Audit events: append-only, per-object sequence, per-object hash chain.
-- Roles (create once, outside this file, as superuser):
--   audit_owner    owns the table; NOLOGIN; never used by app or migration scripts
--   app            INSERT + SELECT only
--   audit_verifier SELECT only; runs audit_verify.sql and the daily digest job
-- Migration scripts must NOT connect as audit_owner or a superuser.

CREATE TABLE audit_events (
    id            bigserial PRIMARY KEY,
    object_type   text        NOT NULL,
    object_id     text        NOT NULL,
    sequence      bigint      NOT NULL,              -- per object, gapless, set by trigger
    action        text        NOT NULL,
    actor_type    text        NOT NULL CHECK (actor_type IN ('user','service','agent','system')),
    actor_id      text        NOT NULL,
    on_behalf_of  text,
    reason_code   text,
    reason_text   text,
    before        jsonb,                              -- masked per field map
    after         jsonb,
    request_id    text,
    idempotency_key text,
    external_ref  text,
    corrects_event_id bigint REFERENCES audit_events(id),
    occurred_at   timestamptz NOT NULL,               -- business time, UTC
    recorded_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
    prev_hash     bytea,                              -- set by trigger
    hash          bytea       NOT NULL,               -- set by trigger
    UNIQUE (object_type, object_id, sequence)
);
CREATE INDEX audit_events_actor_time ON audit_events (actor_id, occurred_at);
CREATE INDEX audit_events_time ON audit_events (occurred_at);

ALTER TABLE audit_events OWNER TO audit_owner;

-- Canonical hash input. Used by the insert trigger and by audit_verify.
CREATE FUNCTION audit_event_hash(e audit_events) RETURNS bytea
LANGUAGE sql IMMUTABLE AS $$
    SELECT sha256(convert_to(concat_ws('|',
        encode(coalesce(e.prev_hash, ''::bytea), 'hex'),
        e.object_type, e.object_id, e.sequence::text, e.action,
        e.actor_type, e.actor_id, coalesce(e.on_behalf_of, ''),
        coalesce(e.reason_code, ''), coalesce(e.reason_text, ''),
        coalesce(e.before::text, ''), coalesce(e.after::text, ''),
        coalesce(e.request_id, ''), coalesce(e.idempotency_key, ''),
        coalesce(e.external_ref, ''), coalesce(e.corrects_event_id::text, ''),
        to_char(e.occurred_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
        to_char(e.recorded_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')
    ), 'UTF8'))
$$;

-- PREVENT 1: sequence and chain are assigned by the database, not the caller.
CREATE FUNCTION audit_events_before_insert() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE last_row audit_events;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.object_type || ':' || NEW.object_id, 0));
    SELECT * INTO last_row FROM audit_events
     WHERE object_type = NEW.object_type AND object_id = NEW.object_id
     ORDER BY sequence DESC LIMIT 1;
    NEW.sequence    := coalesce(last_row.sequence, 0) + 1;
    NEW.prev_hash   := last_row.hash;
    NEW.recorded_at := clock_timestamp();
    NEW.hash        := audit_event_hash(NEW);
    RETURN NEW;
END $$;
CREATE TRIGGER audit_events_chain BEFORE INSERT ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_before_insert();

-- PREVENT 2: no update, delete or truncate, even for the owner.
CREATE FUNCTION audit_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only (% blocked); write a correcting event instead', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER audit_events_no_update_delete BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
CREATE TRIGGER audit_events_no_truncate BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

-- PREVENT 3: privileges. The old `GRANT ALL ... TO app` is what allowed the edit.
REVOKE ALL ON audit_events FROM PUBLIC, app;
GRANT INSERT, SELECT ON audit_events TO app;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO app;
GRANT SELECT ON audit_events TO audit_verifier;

-- DETECT 1: daily digest of every object's chain head, exported to a write-once
-- store (e.g. S3 Object Lock) by a job outside the app's credentials.
CREATE TABLE audit_digests (
    digest_date date PRIMARY KEY,
    last_event_id bigint NOT NULL,
    event_count bigint NOT NULL,
    digest bytea NOT NULL,                -- sha256 over all hashes ordered by id
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE audit_digests OWNER TO audit_owner;
REVOKE ALL ON audit_digests FROM PUBLIC, app;
GRANT SELECT, INSERT ON audit_digests TO audit_verifier;
CREATE TRIGGER audit_digests_immutable BEFORE UPDATE OR DELETE ON audit_digests
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

-- DETECT 2 (needs superuser, install once): block DDL on the audit tables
-- so triggers cannot be dropped or disabled by a migration.
CREATE FUNCTION audit_block_ddl() RETURNS event_trigger
LANGUAGE plpgsql AS $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
        IF r.object_identity IN ('public.audit_events', 'public.audit_digests') THEN
            RAISE EXCEPTION 'DDL on % requires the audit change procedure', r.object_identity;
        END IF;
    END LOOP;
END $$;
CREATE EVENT TRIGGER audit_block_ddl ON ddl_command_end EXECUTE FUNCTION audit_block_ddl();
