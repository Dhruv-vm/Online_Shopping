#!/usr/bin/env bash
# BASKET PostgreSQL Database Restore Script
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <path_to_backup.dump>"
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file '${BACKUP_FILE}' not found."
    exit 1
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-basket_db}"
DB_USER="${DB_USER:-dhruv}"

echo "Restoring database '${DB_NAME}' from '${BACKUP_FILE}' on ${DB_HOST}:${DB_PORT}..."
pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists -v "${BACKUP_FILE}"

echo "Database restore completed successfully."
