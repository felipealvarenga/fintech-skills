CREATE TABLE audit_events (
    id bigserial primary key,
    object_type text not null,
    object_id text not null,
    action text not null,
    actor_id text,
    payload jsonb,
    created_at timestamptz not null default now(),
    -- Tamper-evident hash chain (detection): each row commits to the previous row.
    prev_hash bytea,
    row_hash bytea not null
);

-- PREVENTION 1: least privilege. The app role can only append and read.
-- Never grant UPDATE/DELETE/TRUNCATE, and never run migrations as a role
-- that owns this table or as a superuser (use a separate, reviewed process).
REVOKE ALL ON audit_events FROM PUBLIC;
GRANT SELECT, INSERT ON audit_events TO app;
GRANT USAGE ON SEQUENCE audit_events_id_seq TO app;

-- PREVENTION 2: reject UPDATE/DELETE/TRUNCATE even for roles that have the privilege
-- (e.g. a migration role). Disabling this trigger requires table ownership and
-- is itself detectable via the hash chain below.
CREATE FUNCTION audit_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER audit_events_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TRIGGER audit_events_no_truncate
    BEFORE TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

-- DETECTION 1: hash chain computed on insert (serialized so the chain is linear).
CREATE FUNCTION audit_events_chain() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    last_hash bytea;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext('audit_events_chain'));
    SELECT row_hash INTO last_hash FROM audit_events ORDER BY id DESC LIMIT 1;
    NEW.prev_hash := last_hash;
    NEW.created_at := coalesce(NEW.created_at, now());
    NEW.row_hash := sha256(convert_to(
        coalesce(encode(last_hash, 'hex'), '') || '|' ||
        NEW.id || '|' || NEW.object_type || '|' || NEW.object_id || '|' ||
        NEW.action || '|' || coalesce(NEW.actor_id, '') || '|' ||
        coalesce(NEW.payload::text, '') || '|' || NEW.created_at::text,
        'UTF8'));
    RETURN NEW;
END;
$$;

CREATE TRIGGER audit_events_chain_trg
    BEFORE INSERT ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_chain();

-- DETECTION 2: verification. Returns the ids of rows whose hash or link is wrong,
-- plus gaps in the id sequence (deleted rows). Empty result = chain intact.
-- Run on a schedule and alert on any rows; also periodically export the latest
-- row_hash to storage the DB admins cannot write (WORM bucket / external log),
-- otherwise someone who rewrites the whole chain cannot be caught.
CREATE FUNCTION audit_events_verify()
RETURNS TABLE (bad_id bigint, problem text)
LANGUAGE sql STABLE AS $$
    WITH ordered AS (
        SELECT e.*,
               lag(e.row_hash) OVER (ORDER BY e.id) AS expected_prev,
               lag(e.id)       OVER (ORDER BY e.id) AS prev_id
        FROM audit_events e
    )
    SELECT id, 'broken link or deleted row'
    FROM ordered
    WHERE prev_hash IS DISTINCT FROM expected_prev
    UNION ALL
    SELECT id, 'row contents modified'
    FROM ordered
    WHERE row_hash IS DISTINCT FROM sha256(convert_to(
        coalesce(encode(prev_hash, 'hex'), '') || '|' ||
        id || '|' || object_type || '|' || object_id || '|' ||
        action || '|' || coalesce(actor_id, '') || '|' ||
        coalesce(payload::text, '') || '|' || created_at::text, 'UTF8'))
    UNION ALL
    SELECT id, 'gap in id sequence (possible deletion)'
    FROM ordered
    WHERE prev_id IS NOT NULL AND id <> prev_id + 1
$$;
