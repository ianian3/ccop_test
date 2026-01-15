#!/bin/bash
# Database initialization script for AgensGraph

set -e

echo "Initializing AgensGraph database..."

# Wait for PostgreSQL to be ready
until pg_isready -U ${POSTGRES_USER}; do
  echo "Waiting for database to be ready..."
  sleep 2
done

# Create graph extension
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS age;
    LOAD 'age';
    SET search_path = ag_catalog, "$user", public;
EOSQL

echo "AgensGraph initialization complete!"
