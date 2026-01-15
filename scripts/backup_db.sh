#!/bin/bash
# Automated database backup script

set -e

# Configuration
BACKUP_DIR="/var/backups/agensgraph"
DB_NAME="${DB_NAME:-ccopdb}"
DB_USER="${DB_USER:-ccop}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_backup_$TIMESTAMP.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
echo "Target: $BACKUP_FILE"

# Perform backup
pg_dump -U "$DB_USER" -d "$DB_NAME" -F c -f "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

echo "Backup completed: $BACKUP_FILE"

# Remove backups older than 30 days
find "$BACKUP_DIR" -name "${DB_NAME}_backup_*.sql.gz" -mtime +30 -delete
echo "Old backups cleaned up (>30 days)"

# Display backup size
du -h "$BACKUP_FILE"
