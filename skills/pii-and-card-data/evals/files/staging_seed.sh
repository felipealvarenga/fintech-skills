#!/bin/bash
# Refresh staging with production data
pg_dump "$PROD_DATABASE_URL" | psql "$STAGING_DATABASE_URL"
