#!/bin/bash
# Customer360 PostgreSQL Backup Script
# Usage: ./scripts/backup.sh [output_dir]
# Default output directory: ./backups/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/customer360_$TIMESTAMP.sql.gz"
DB_NAME="${PGDATABASE:-customer360}"
DB_USER="${PGUSER:-customer360}"
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
RETENTION_DAYS=7
RETENTION_WEEKS=4

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting PostgreSQL backup at $(date)"
echo "[backup] Database: $DB_NAME on $DB_HOST:$DB_PORT"
echo "[backup] Output: $BACKUP_FILE"

# Perform the backup
PGPASSWORD="${PGPASSWORD:-}" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-acl \
    --verbose \
    2> /dev/null | gzip > "$BACKUP_FILE"

# Verify backup integrity
if [ -f "$BACKUP_FILE" ]; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[backup] Backup completed: $BACKUP_FILE ($FILE_SIZE)"
    
    # Test the backup can be read
    if gunzip -t "$BACKUP_FILE" 2>/dev/null; then
        echo "[backup] Backup integrity verified"
    else
        echo "[backup] ERROR: Backup integrity check failed!"
        exit 1
    fi
else
    echo "[backup] ERROR: Backup file not created!"
    exit 1
fi

# Cleanup old backups (daily)
find "$BACKUP_DIR" -name "customer360_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Keep weekly backups longer
find "$BACKUP_DIR" -name "customer360_*.sql.gz" -mtime +$((RETENTION_WEEKS * 7)) -delete

echo "[backup] Cleanup completed (retention: $RETENTION_DAYS days, $RETENTION_WEEKS weeks)"
echo "[backup] Backup finished successfully at $(date)"
