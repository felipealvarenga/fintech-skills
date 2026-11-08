CREATE TABLE pix_charges (
    txid          VARCHAR(35) PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES orders(id),
    amount_minor  BIGINT NOT NULL,
    payload       TEXT NOT NULL,
    status        VARCHAR(16) NOT NULL,       -- active | paid | expired
    end_to_end_id CHAR(32) UNIQUE,
    expires_at    TIMESTAMP NOT NULL
);

CREATE TABLE pix_payments (
    end_to_end_id CHAR(32) PRIMARY KEY,       -- uniqueness makes the webhook idempotent
    txid          VARCHAR(35) NOT NULL,
    amount_minor  BIGINT NOT NULL,
    outcome       VARCHAR(24) NOT NULL        -- paid | refund_requested | unknown_charge
);
