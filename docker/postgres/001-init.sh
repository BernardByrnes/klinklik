#!/bin/sh
set -eu

: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD must be set for the local application role}"

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    -v app_password="$POSTGRES_APP_PASSWORD" \
    -f /docker-entrypoint-initdb.d/002-init.sql
