-- Run as audit_verifier at least daily, and alert on any returned row.
-- Detects edited rows, deleted rows (sequence gaps / broken chain), and
-- tail truncation or edits to history already covered by a stored digest.

-- 1. Chain check: every row's hash matches its content, links to its predecessor,
--    and sequences are gapless per object.
CREATE OR REPLACE VIEW audit_chain_violations AS
SELECT e.id, e.object_type, e.object_id, e.sequence,
       CASE
         WHEN e.hash IS DISTINCT FROM audit_event_hash(e)            THEN 'content_modified'
         WHEN e.sequence = 1 AND e.prev_hash IS NOT NULL             THEN 'bad_first_link'
         WHEN e.sequence > 1 AND p.id IS NULL                        THEN 'missing_predecessor'
         WHEN e.sequence > 1 AND e.prev_hash IS DISTINCT FROM p.hash THEN 'broken_link'
       END AS problem
FROM audit_events e
LEFT JOIN audit_events p
       ON p.object_type = e.object_type AND p.object_id = e.object_id
      AND p.sequence = e.sequence - 1
WHERE e.hash IS DISTINCT FROM audit_event_hash(e)
   OR (e.sequence = 1 AND e.prev_hash IS NOT NULL)
   OR (e.sequence > 1 AND (p.id IS NULL OR e.prev_hash IS DISTINCT FROM p.hash));

-- 2. Digest check: recompute the digest for each stored day and compare.
--    Catches deletion of a whole object's tail, which the chain alone cannot see.
CREATE OR REPLACE VIEW audit_digest_violations AS
SELECT d.digest_date, d.event_count AS expected_count, x.cnt AS actual_count
FROM audit_digests d
CROSS JOIN LATERAL (
    SELECT count(*) AS cnt,
           sha256(convert_to(coalesce(string_agg(encode(hash, 'hex'), '' ORDER BY id), ''), 'UTF8')) AS dg
    FROM audit_events WHERE id <= d.last_event_id
) x
WHERE x.cnt <> d.event_count OR x.dg <> d.digest;

-- 3. Daily digest writer (run by audit_verifier, then ship the row to the write-once store).
CREATE OR REPLACE FUNCTION audit_write_digest(day date DEFAULT current_date) RETURNS void
LANGUAGE sql AS $$
    INSERT INTO audit_digests (digest_date, last_event_id, event_count, digest)
    SELECT day, coalesce(max(id), 0), count(*),
           sha256(convert_to(coalesce(string_agg(encode(hash, 'hex'), '' ORDER BY id), ''), 'UTF8'))
    FROM audit_events;
$$;
