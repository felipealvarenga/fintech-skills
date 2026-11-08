-- Cache of the ledger balance, minor units (e.g. centavos). Source of truth is `postings`.
ALTER TABLE users ADD COLUMN balance_minor BIGINT NOT NULL DEFAULT 0;

CREATE TABLE ledger_state (closed_through DATE);  -- single row; NULL = nothing closed
INSERT INTO ledger_state VALUES (NULL);

CREATE TABLE journal_entries (
  id             BIGSERIAL PRIMARY KEY,
  external_ref   TEXT NOT NULL UNIQUE,
  effective_date DATE NOT NULL,
  recorded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  reverses_ref   TEXT REFERENCES journal_entries(external_ref),
  description    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE postings (
  id           BIGSERIAL PRIMARY KEY,
  entry_id     BIGINT NOT NULL REFERENCES journal_entries(id),
  account      TEXT NOT NULL,
  side         TEXT NOT NULL CHECK (side IN ('debit','credit')),
  amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
  currency     CHAR(3) NOT NULL
);
CREATE INDEX postings_account_idx ON postings (account, currency);

-- Immutability
CREATE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'ledger rows are immutable'; END $$ LANGUAGE plpgsql;
CREATE TRIGGER journal_entries_immutable BEFORE UPDATE OR DELETE ON journal_entries
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER postings_immutable BEFORE UPDATE OR DELETE ON postings
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
-- Also: REVOKE UPDATE, DELETE ON journal_entries, postings FROM <app_role>;

-- Balanced per currency, checked at commit
CREATE FUNCTION check_entry_balanced() RETURNS trigger AS $$
BEGIN
  IF (SELECT count(*) FROM postings WHERE entry_id = NEW.entry_id) < 2 THEN
    RAISE EXCEPTION 'entry % has fewer than two postings', NEW.entry_id;
  END IF;
  IF EXISTS (SELECT 1 FROM postings WHERE entry_id = NEW.entry_id GROUP BY currency
             HAVING sum(CASE side WHEN 'debit' THEN amount_minor ELSE -amount_minor END) <> 0) THEN
    RAISE EXCEPTION 'entry % does not balance per currency', NEW.entry_id;
  END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;
CREATE CONSTRAINT TRIGGER postings_balanced AFTER INSERT ON postings
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_entry_balanced();

-- Cutover: for each user with an existing balance, post an opening entry
-- (debit 3010 migration equity, credit 2010:<user_id>), external_ref = 'opening:<user_id>',
-- then run wallet.reconcile for every user before dropping the old `balance` column.
