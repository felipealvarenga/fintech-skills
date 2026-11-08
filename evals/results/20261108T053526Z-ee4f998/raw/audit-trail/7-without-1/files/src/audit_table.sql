CREATE TABLE audit_events (
    id bigserial primary key,
    object_type text not null,
    object_id text not null,
    action text not null,
    actor_id text,
    payload jsonb,
    created_at timestamptz not null default now(),
    prev_hash bytea,
    row_hash bytea not null
);

-- PREVENT -------------------------------------------------------------
-- The app role may only append and read. No UPDATE/DELETE/TRUNCATE.
REVOKE ALL ON audit_events FROM PUBLIC;
GRANT SELECT, INSERT ON audit_events TO app;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO app;

-- Block mutation even for the table owner / migration roles.
CREATE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

-- DETECT --------------------------------------------------------------
-- Hash chain: each row's hash covers its content and the previous row's hash.
-- Any edit, deletion in the middle, or insertion out of order breaks the chain.
CREATE FUNCTION audit_events_row_hash(e audit_events, prev bytea) RETURNS bytea AS $$
    SELECT sha256(convert_to(
        coalesce(encode(prev, 'hex'), '') || '|' ||
        e.id || '|' || e.object_type || '|' || e.object_id || '|' || e.action || '|' ||
        coalesce(e.actor_id, '') || '|' || coalesce(e.payload::text, '') || '|' ||
        e.created_at::text, 'UTF8'));
$$ LANGUAGE sql IMMUTABLE;

CREATE FUNCTION audit_events_chain() RETURNS trigger AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('audit_events_chain'));  -- serialize appends
    SELECT row_hash INTO NEW.prev_hash FROM audit_events ORDER BY id DESC LIMIT 1;
    NEW.row_hash := audit_events_row_hash(NEW, NEW.prev_hash);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_chain
    BEFORE INSERT ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_chain();

-- Run on a schedule (e.g. hourly) and alert on any returned rows.
CREATE FUNCTION audit_events_verify() RETURNS TABLE (bad_id bigint, reason text) AS $$
    SELECT id,
           CASE WHEN prev_hash IS DISTINCT FROM lag(row_hash) OVER (ORDER BY id)
                THEN 'chain broken (row removed or altered before this one)'
                ELSE 'row content does not match its hash' END
    FROM (
        SELECT e.*, audit_events_row_hash(e, e.prev_hash) AS expected
        FROM audit_events e
    ) x
    WHERE row_hash IS DISTINCT FROM expected
       OR prev_hash IS DISTINCT FROM lag(row_hash) OVER (ORDER BY id);
$$ LANGUAGE sql STABLE;

-- Detect tampering with the protections themselves (DROP/ALTER TRIGGER, ALTER TABLE...).
CREATE TABLE audit_ddl_log (
    id bigserial primary key,
    at timestamptz not null default now(),
    username text not null default session_user,
    command_tag text,
    object_identity text
);

CREATE FUNCTION audit_events_ddl_watch() RETURNS event_trigger AS $$
DECLARE r record;
BEGIN
    FOR r IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
        IF r.object_identity LIKE '%audit_events%' THEN
            INSERT INTO audit_ddl_log(command_tag, object_identity)
            VALUES (r.command_tag, r.object_identity);
            RAISE WARNING 'DDL on audit_events by %: %', session_user, r.command_tag;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

CREATE EVENT TRIGGER audit_events_ddl_watch ON ddl_command_end
    EXECUTE FUNCTION audit_events_ddl_watch();
