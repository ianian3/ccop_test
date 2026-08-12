#!/bin/bash
# Database initialization script for AgensGraph

set -e

echo "Initializing AgensGraph database..."

# Wait for PostgreSQL to be ready
until pg_isready -U ${POSTGRES_USER}; do
  echo "Waiting for database to be ready..."
  sleep 2
done

# Create graph (bitnine AgensGraph 네이티브 — age extension 불필요)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE GRAPH IF NOT EXISTS tccop_graph_v6;
    SET graph_path = tccop_graph_v6;
EOSQL

echo "AgensGraph initialization complete!"
