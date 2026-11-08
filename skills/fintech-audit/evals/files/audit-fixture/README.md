# audit-fixture

A small payments module with planted defects, used by the fintech-audit evals. Nothing here is
real. Planted defects (code, file): FLOAT_MONEY billing.py, ROUND_MONEY billing.py,
DIV100 billing.py, RANDOM_IDEMPOTENCY charges.py, RATE_FLOAT charges.py, BALANCE_UPDATE wallet.py,
BODY_LOG webhooks.py, PARSED_BODY_VERIFY webhooks.py, CVV_FIELD models.py,
DIGITS_ONLY_CNPJ documents.py, PAID_ON_ISSUE boleto.py, WALL_CLOCK_MONEY settlement.py.
