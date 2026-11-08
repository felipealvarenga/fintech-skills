-- Run as the app role after loading audit_table.sql. Each block must behave as commented.
-- Intended for a CI database; uses savepoints so failures are asserted, not fatal.
\set ON_ERROR_STOP on
SET ROLE app;

INSERT INTO audit_events (object_type, object_id, action, actor_type, actor_id, occurred_at)
VALUES ('limit','t1','set','user','u1', now()), ('limit','t1','set','user','u1', now());

DO $$ BEGIN
    IF (SELECT array_agg(sequence ORDER BY sequence) FROM audit_events WHERE object_id='t1') <> ARRAY[1,2] THEN
        RAISE EXCEPTION 'sequence not gapless';
    END IF;
    IF (SELECT count(*) FROM audit_events_verify()) <> 0 THEN
        RAISE EXCEPTION 'fresh chain should verify clean';
    END IF;
    BEGIN
        UPDATE audit_events SET action='x' WHERE object_id='t1';
        RAISE EXCEPTION 'app UPDATE succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        DELETE FROM audit_events WHERE object_id='t1';
        RAISE EXCEPTION 'app DELETE succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
    BEGIN
        TRUNCATE audit_events;
        RAISE EXCEPTION 'app TRUNCATE succeeded';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;

-- Detection: as owner, disable the triggers, tamper, and expect verify to flag it.
RESET ROLE;
SET ROLE audit_owner;
ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete;
UPDATE audit_events SET action='tampered' WHERE object_id='t1' AND sequence=1;
DO $$ BEGIN
    IF (SELECT count(*) FROM audit_events_verify()) = 0 THEN RAISE EXCEPTION 'tamper not detected'; END IF;
    IF (SELECT count(*) FROM audit_guard_status) = 0 THEN RAISE EXCEPTION 'disabled trigger not reported'; END IF;
END $$;
-- Test DB is discarded afterwards; do not run against shared data.
