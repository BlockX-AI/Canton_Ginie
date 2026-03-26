#!/bin/bash
# init_databases.sh — Create Ginie + Canton databases in PostgreSQL
#
# Docker: mount into /docker-entrypoint-initdb.d/00-init-databases.sh
# Manual: PGPASSWORD=password bash backend/scripts/init_databases.sh

set -e

echo "Creating databases for Ginie Canton..."

# Create canton_sandbox database (Canton participant storage)
psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d postgres <<-EOSQL
    SELECT 'canton_sandbox already exists' WHERE EXISTS (SELECT FROM pg_database WHERE datname = 'canton_sandbox');
    CREATE DATABASE canton_sandbox;
EOSQL
echo "  canton_sandbox: OK"

# Create ginie_daml database (Ginie application state)
psql -v ON_ERROR_STOP=0 -U "$POSTGRES_USER" -d postgres <<-EOSQL
    SELECT 'ginie_daml already exists' WHERE EXISTS (SELECT FROM pg_database WHERE datname = 'ginie_daml');
    CREATE DATABASE ginie_daml;
EOSQL
echo "  ginie_daml: OK"

# Create reference tables in ginie_daml (SQLAlchemy also creates these on startup)
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d ginie_daml -f /docker-entrypoint-initdb.d/01-init.sql 2>/dev/null || true

echo "Database initialization complete."
