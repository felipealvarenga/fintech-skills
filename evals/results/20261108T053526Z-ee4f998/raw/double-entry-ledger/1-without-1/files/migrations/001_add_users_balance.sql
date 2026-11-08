ALTER TABLE users
    ADD COLUMN balance NUMERIC(12, 2) NOT NULL DEFAULT 0
    CONSTRAINT users_balance_non_negative CHECK (balance >= 0);
