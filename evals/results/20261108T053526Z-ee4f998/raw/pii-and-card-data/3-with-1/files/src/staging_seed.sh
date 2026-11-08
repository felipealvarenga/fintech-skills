#!/bin/bash
# Seed staging with SYNTHETIC data. Production data must never be copied here.
set -euo pipefail
: "${STAGING_DATABASE_URL:?set STAGING_DATABASE_URL}"
COUNT="${1:-500}"

# Guard: refuse if staging points at the same database as production.
if [ -n "${PROD_DATABASE_URL:-}" ] && [ "$PROD_DATABASE_URL" = "$STAGING_DATABASE_URL" ]; then
  echo "refusing: STAGING_DATABASE_URL equals PROD_DATABASE_URL" >&2; exit 1
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -I - "$DIR" "$COUNT" <<'PY' | psql "$STAGING_DATABASE_URL" -v ON_ERROR_STOP=1
import sys
sys.path.insert(0, sys.argv[1])
from synthetic_data import gen_customers
rows = gen_customers(int(sys.argv[2]))
q = lambda s: "'" + str(s).replace("'", "''") + "'"
print("BEGIN;")
print("CREATE TABLE IF NOT EXISTS customers (id int primary key, name text, email text, cpf text,"
      " card_token text, card_brand text, card_last4 text, card_exp text);")
for r in rows:
    print(f"INSERT INTO customers VALUES ({r['id']},{q(r['name'])},{q(r['email'])},{q(r['cpf'])},"
          f"{q(r['card_token'])},{q(r['card_brand'])},{q(r['card_last4'])},{q(r['card_exp'])})"
          " ON CONFLICT (id) DO NOTHING;")
print("COMMIT;")
PY
