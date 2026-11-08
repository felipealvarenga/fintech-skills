-- Audit events: append-only, hash-chained per object.
-- Run as a dedicated owner role (audit_owner), NOT as the app or the migration role.
-- Roles: audit_owner (owns table), app (INSERT/SELECT only), audit_verifier (SELECT only, used by the check job).

CREATE TABLE audit_events (
    id            bigserial primary key,
    object_type   text not null,
    object_id     text not null,
    sequence      bigint not null,                  -- per-object, gapless, set by trigger
    action        text not null,
    actor_type    text not null check (actor_type in ('user','service','agent','system')),
    actor_id      text,
    on_behalf_of  text,
    payload       jsonb,                            -- before/after or command, masked
    reason_code   text,
    request_id    text,
    occurred_at   timestamptz not null,
    recorded_at   timestamptz not null default now(),
    prev_hash     bytea,                            -- hash of previous event of same object
    row_hash      bytea not null,
    unique (object_type, object_id, sequence)
);

-- Assign sequence and hash chain inside the inserting transaction.
CREATE FUNCTION audit_events_chain() RETURNS trigger AS $$
DECLARE
    last_seq  bigint;
    last_hash bytea;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(NEW.object_type || ':' || NEW.object_id, 0));
    SELECT sequence, row_hash INTO last_seq, last_hash
      FROM audit_events
     WHERE object_type = NEW.object_type AND object_id = NEW.object_id
     ORDER BY sequence DESC LIMIT 1;

    NEW.sequence    := COALESCE(last_seq, 0) + 1;
    NEW.recorded_at := now();
    NEW.prev_hash   := last_hash;
    NEW.row_hash    := audit_events_hash(NEW.*, last_hash);
    RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE FUNCTION audit_events_hash(e audit_events, prev bytea) RETURNS bytea AS $$
    SELECT sha256(convert_to(concat_ws('|',
        e.object_type, e.object_id, e.sequence, e.action, e.actor_type,
        coalesce(e.actor_id,''), coalesce(e.on_behalf_of,''),
        coalesce(e.payload::text,''), coalesce(e.reason_code,''),
        coalesce(e.request_id,''), e.occurred_at, e.recorded_at,
        coalesce(encode(prev,'hex'),'')), 'UTF8'))
$$ LANGUAGE sql IMMUTABLE;

CREATE TRIGGER audit_events_chain_bi
    BEFORE INSERT ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_chain();

-- PREVENT (layer 1): privileges. No UPDATE/DELETE/TRUNCATE for anyone but the owner.
REVOKE ALL ON audit_events FROM PUBLIC, app;
GRANT INSERT, SELECT ON audit_events TO app;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO app;
GRANT SELECT ON audit_events TO audit_verifier;

-- PREVENT (layer 2): triggers block edits even by the owner or a migration run as owner.
CREATE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only (% blocked); correct with a new event', TG_OP;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

-- DETECT (layer 1): chain verification. Returns one row per broken event; empty = intact.
-- Catches edited rows, deleted rows (sequence gap / broken link) and rewritten history.
CREATE FUNCTION audit_events_verify() RETURNS TABLE (id bigint, object_type text, object_id text, sequence bigint, problem text) AS $$
    WITH e AS (
        SELECT a.*,
               lag(a.row_hash) OVER w AS expected_prev,
               lag(a.sequence) OVER w AS prev_seq
          FROM audit_events a
        WINDOW w AS (PARTITION BY a.object_type, a.object_id ORDER BY a.sequence)
    )
    SELECT e.id, e.object_type, e.object_id, e.sequence,
           CASE
             WHEN e.row_hash IS DISTINCT FROM audit_events_hash(e::audit_events, e.prev_hash) THEN 'row content altered'
             WHEN e.prev_hash IS DISTINCT FROM e.expected_prev THEN 'chain link broken'
             WHEN e.sequence <> coalesce(e.prev_seq, 0) + 1 THEN 'sequence gap (deleted event)'
           END
      FROM e
     WHERE e.row_hash IS DISTINCT FROM audit_events_hash(e::audit_events, e.prev_hash)
        OR e.prev_hash IS DISTINCT FROM e.expected_prev
        OR e.sequence <> coalesce(e.prev_seq, 0) + 1;
$$ LANGUAGE sql STABLE;

-- DETECT (layer 2): the chain alone cannot reveal a wholesale rewrite or a dropped trigger by a
-- superuser. Daily, a job running as audit_verifier must (a) run audit_events_verify(), and
-- (b) export a digest to a write-once store outside the app's reach (see src/audit_digest.sql).
CREATE TABLE audit_digest_log (
    digest_date date primary key,
    last_event_id bigint not null,
    event_count bigint not null,
    digest bytea not null
);
GRANT SELECT ON audit_digest_log TO audit_verifier;

CREATE VIEW audit_daily_digest AS
SELECT current_date AS digest_date,
       max(id) AS last_event_id,
       count(*) AS event_count,
       sha256(convert_to(string_agg(encode(row_hash,'hex'), '' ORDER BY id), 'UTF8')) AS digest
  FROM audit_events;
GRANT SELECT ON audit_daily_digest TO audit_verifier;

-- DETECT (layer 3): alert on trigger tampering. Run from the check job; any row returned = page someone.
CREATE VIEW audit_guard_status AS
SELECT 'trigger missing or disabled: ' || t AS problem
  FROM unnest(ARRAY['audit_events_chain_bi','audit_events_no_update_delete','audit_events_no_truncate']) t
 WHERE NOT EXISTS (
        SELECT 1 FROM pg_trigger
         WHERE tgrelid = 'audit_events'::regclass AND tgname = t AND tgenabled = 'O')
UNION ALL
SELECT 'unexpected privilege: ' || grantee || ' has ' || privilege_type
  FROM information_schema.role_table_grants
 WHERE table_name = 'audit_events'
   AND privilege_type IN ('UPDATE','DELETE','TRUNCATE')
   AND grantee <> current_user;
GRANT SELECT ON audit_guard_status TO audit_verifier;
