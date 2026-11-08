-- Wallet ledger. users.balance_minor is a CACHE of the derived balance (see reconcile()).
ALTER TABLE users ADD COLUMN balance_minor BIGINT NOT NULL DEFAULT 0 CHECK (balance_minor >= 0);

CREATE TABLE ledger_accounts (
    id          BIGSERIAL PRIMARY KEY,
    code        TEXT NOT NULL,                 -- e.g. 2010 customer balances, 4010 revenue, 1020 receivable
    user_id     TEXT REFERENCES users(id),     -- set for per-user wallet accounts
    currency    CHAR(3) NOT NULL,              -- one currency per account
    normal_side TEXT NOT NULL CHECK (normal_side IN ('debit','credit')),
    UNIQUE (code, user_id, currency)
);

CREATE TABLE ledger_entries (
    id             BIGSERIAL PRIMARY KEY,
    external_ref   TEXT NOT NULL UNIQUE,       -- idempotency key / processor event id
    effective_date DATE NOT NULL,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    reverses_id    BIGINT REFERENCES ledger_entries(id)
);

CREATE TABLE ledger_postings (
    id           BIGSERIAL PRIMARY KEY,
    entry_id     BIGINT NOT NULL REFERENCES ledger_entries(id),
    account_id   BIGINT NOT NULL REFERENCES ledger_accounts(id),
    side         TEXT NOT NULL CHECK (side IN ('debit','credit')),
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency     CHAR(3) NOT NULL
);

CREATE TABLE ledger_state (singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton), closed_through DATE);
INSERT INTO ledger_state (closed_through) VALUES (NULL);

-- Immutability (rule 1). Also REVOKE UPDATE, DELETE on these tables from the app role.
CREATE FUNCTION ledger_immutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'ledger rows are immutable; post a reversal'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER entries_immutable  BEFORE UPDATE OR DELETE ON ledger_entries  FOR EACH ROW EXECUTE FUNCTION ledger_immutable();
CREATE TRIGGER postings_immutable BEFORE UPDATE OR DELETE ON ledger_postings FOR EACH ROW EXECUTE FUNCTION ledger_immutable();

-- Balanced per currency, at least two postings (rule 2), checked at commit.
CREATE FUNCTION ledger_check_balanced() RETURNS trigger AS $$
BEGIN
  IF (SELECT count(*) FROM ledger_postings WHERE entry_id = NEW.entry_id) < 2 THEN
    RAISE EXCEPTION 'entry % has fewer than two postings', NEW.entry_id;
  END IF;
  IF EXISTS (SELECT 1 FROM ledger_postings WHERE entry_id = NEW.entry_id
             GROUP BY currency
             HAVING sum(CASE side WHEN 'debit' THEN amount_minor ELSE -amount_minor END) <> 0) THEN
    RAISE EXCEPTION 'entry % is unbalanced', NEW.entry_id;
  END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER postings_balanced AFTER INSERT ON ledger_postings
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger_check_balanced();
