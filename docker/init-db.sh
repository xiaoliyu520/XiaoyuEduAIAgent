#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE judge0;
    GRANT ALL PRIVILEGES ON DATABASE judge0 TO xiaoyu;
EOSQL
