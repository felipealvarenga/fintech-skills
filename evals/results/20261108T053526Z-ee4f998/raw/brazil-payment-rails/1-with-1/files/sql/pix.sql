CREATE TABLE pix_charges (
    txid           VARCHAR(35) PRIMARY KEY,
    order_id       BIGINT NOT NULL,
    amount_minor   BIGINT NOT NULL,
    payload        TEXT NOT NULL,
    status         VARCHAR(10) NOT NULL,          -- active | paid | expired
    expires_at     VARCHAR(40) NOT NULL,          -- ISO 8601 UTC (use TIMESTAMPTZ in Postgres)
    end_to_end_id  VARCHAR(32)
);

CREATE TABLE pix_payments (
    end_to_end_id  VARCHAR(32) PRIMARY KEY,       -- idempotency key
    txid           VARCHAR(35),
    order_id       BIGINT,
    amount_minor   BIGINT NOT NULL,
    refunded_minor BIGINT NOT NULL DEFAULT 0,
    outcome        VARCHAR(12) NOT NULL           -- paid | refunded | exception
);

CREATE TABLE pix_refunds (
    refund_id      VARCHAR(35) PRIMARY KEY,
    end_to_end_id  VARCHAR(32) NOT NULL,
    amount_minor   BIGINT NOT NULL,
    reason         TEXT
);

CREATE TABLE pix_exceptions (
    id             INTEGER PRIMARY KEY,
    end_to_end_id  VARCHAR(32) NOT NULL,
    txid           VARCHAR(35),
    reason         TEXT NOT NULL
);
