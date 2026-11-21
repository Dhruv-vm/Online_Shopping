#!/usr/bin/env bash
# BASKET PostgreSQL Database Backup Script
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/basket_db_${TIMESTAMP}.dump"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-basket_db}"
DB_USER="${DB_USER:-dhruv}"

echo "Starting PostgreSQL backup for database '${DB_NAME}' on ${DB_HOST}:${DB_PORT}..."
pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -F c -b -v -f "${BACKUP_FILE}" "${DB_NAME}"

echo "Backup completed successfully: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"
