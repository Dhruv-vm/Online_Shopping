#!/usr/bin/env bash
# Verify that Alembic revisions upgrade, downgrade and re-apply cleanly.
#
# Runs ONLY against a throwaway database (default: basket_migration_verify),
# which it creates from scratch and drops at the end. It refuses any database
# name that does not end in _verify, so it can never touch basket_db,
# basket_demo or production.
#
# For each revision in REVISIONS it checks:
#   upgrade(prev -> rev) -> downgrade(rev -> prev): schema identical to before
#   re-upgrade(prev -> rev): schema identical to the first upgrade
# Then a sequential rollback head -> BASE_REV and re-apply -> head, and
# integrity checks (invalid constraints, FK columns without an index,
# Alembic model drift).
#
# Usage: scripts/verify-migrations.sh [db_name]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
DB="${1:-basket_migration_verify}"
BASE_REV="0030_dukaan_vs_dukaan"
REVISIONS=(0031_marketplace_completion 0032_admin_audit_log 0033_retailer_onboarding_media 0034_foreign_key_indexes)
NEW_TABLES="data_quarantine price_alerts group_buy_templates group_buy_campaigns admin_audit_logs price_history_ticks retailers retailer_verification_documents product_listings"

[[ "$DB" == *_verify ]] || { echo "Refusing: database name must end in _verify (got '$DB')." >&2; exit 2; }

PSQL="$(command -v psql || echo /opt/homebrew/bin/psql)"
PG_DUMP="$(command -v pg_dump || echo /opt/homebrew/bin/pg_dump)"
ENV_URL="$(grep -E '^DATABASE_URL=' "$BACKEND/.env" | cut -d= -f2-)"
BASE_URL="${ENV_URL%/*}"                     # driver://user:pass@host:port
QUERY="${ENV_URL##*/}"; [[ "$QUERY" == *\?* ]] && QUERY="?${QUERY#*\?}" || QUERY=""
ASYNC_URL="$BASE_URL/$DB$QUERY"
SYNC_URL="$(echo "$BASE_URL" | sed 's/+asyncpg//')"
ADMIN_URL="$SYNC_URL/postgres$QUERY"
DB_URL="$SYNC_URL/$DB$QUERY"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

psql_admin() { "$PSQL" "$ADMIN_URL" -X -q -v ON_ERROR_STOP=1 "$@"; }
psql_db()    { "$PSQL" "$DB_URL" -X -q -A -t -v ON_ERROR_STOP=1 "$@"; }
alembic()    { (cd "$BACKEND" && DATABASE_URL="$ASYNC_URL" .venv/bin/alembic "$@" >/dev/null 2>&1); }
snapshot()   { "$PG_DUMP" "$DB_URL" --schema-only --no-owner --no-privileges \
                 | grep -vE '^(--|SET |SELECT pg_catalog|\\(un)?restrict )' | sed '/^$/d' > "$WORK/$1.sql"; }
same()       { if diff -q "$WORK/$1.sql" "$WORK/$2.sql" >/dev/null; then echo "  PASS  $3";
               else echo "  FAIL  $3"; diff "$WORK/$1.sql" "$WORK/$2.sql" | head -20; FAILED=1; fi; }
FAILED=0

echo "== Fresh database $DB"
psql_admin -c "DROP DATABASE IF EXISTS \"$DB\";" -c "CREATE DATABASE \"$DB\";"
alembic upgrade "$BASE_REV"
snapshot "$BASE_REV"

prev="$BASE_REV"
for rev in "${REVISIONS[@]}"; do
  echo "== $rev"
  alembic upgrade "$rev";   snapshot "$rev.up1";  echo "  PASS  upgrade $prev -> $rev"
  alembic downgrade "$prev"; snapshot "$rev.down"
  same "$prev" "$rev.down" "downgrade $rev -> $prev restores the previous schema exactly"
  alembic upgrade "$rev";   snapshot "$rev.up2"
  same "$rev.up1" "$rev.up2" "re-upgrade $prev -> $rev reproduces the same schema"
  cp "$WORK/$rev.up1.sql" "$WORK/$rev.sql"
  prev="$rev"
done
HEAD_REV="$prev"

echo "== Sequential rollback $HEAD_REV -> $BASE_REV and re-apply"
alembic downgrade "$BASE_REV"; snapshot seq.down
same "$BASE_REV" seq.down "full rollback to $BASE_REV matches the original schema"
alembic upgrade head; snapshot seq.up
same "$HEAD_REV" seq.up "re-apply to head matches the first upgrade"
CURRENT="$(cd "$BACKEND" && DATABASE_URL="$ASYNC_URL" .venv/bin/alembic current 2>/dev/null | tail -1)"
echo "  INFO  alembic current: $CURRENT"

echo "== Integrity"
INVALID="$(psql_db -c "SELECT conrelid::regclass||'.'||conname FROM pg_constraint WHERE NOT convalidated;")"
[[ -z "$INVALID" ]] && echo "  PASS  no NOT VALID constraints" || { echo "  FAIL  invalid constraints: $INVALID"; FAILED=1; }

TABLES_SQL="'$(echo $NEW_TABLES | sed "s/ /','/g")'"
echo "  INFO  foreign keys on tables touched by ${REVISIONS[*]}:"
psql_db -c "
  SELECT '        '||c.conrelid::regclass||'('||a.attname||') -> '||c.confrelid::regclass
         ||' ON DELETE '||CASE c.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
                                             WHEN 'r' THEN 'RESTRICT' ELSE 'NO ACTION' END
  FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
  WHERE c.contype='f' AND c.conrelid::regclass::text IN ($TABLES_SQL)
  ORDER BY 1;"

UNINDEXED="$(psql_db -c "
  SELECT c.conrelid::regclass||'('||a.attname||')'
  FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1]
  WHERE c.contype='f' AND c.conrelid::regclass::text IN ($TABLES_SQL)
    AND NOT EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid=c.conrelid
                    AND i.indkey[0]=c.conkey[1] AND i.indpred IS NULL)
  ORDER BY 1;")"
if [[ -z "$UNINDEXED" ]]; then echo "  PASS  every FK column on these tables has a full (non-partial) leading index"
else echo "  FAIL  FK columns without a full leading index:"; echo "$UNINDEXED" | sed 's/^/        /'; FAILED=1; fi

if (cd "$BACKEND" && DATABASE_URL="$ASYNC_URL" .venv/bin/alembic check > "$WORK/check.txt" 2>&1); then
  echo "  PASS  alembic check: models match the migrated schema"
else
  echo "  INFO  alembic check reports drift (pre-existing items are listed in BACKEND_AUDIT §0.5):"
  grep -oE "\('(add|remove|modify)_[a-z_]+', [^)]{0,120}" "$WORK/check.txt" | sed 's/^/        /' | head -40
fi

psql_admin -c "DROP DATABASE IF EXISTS \"$DB\";"
echo "== Dropped $DB"
[[ $FAILED -eq 0 ]] && echo "RESULT: ALL MIGRATION CHECKS PASSED" || { echo "RESULT: FAILURES ABOVE"; exit 1; }
