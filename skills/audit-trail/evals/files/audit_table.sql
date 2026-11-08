CREATE TABLE audit_events (
    id bigserial primary key,
    object_type text not null,
    object_id text not null,
    action text not null,
    actor_id text,
    payload jsonb,
    created_at timestamptz default now()
);
GRANT ALL ON audit_events TO app;
