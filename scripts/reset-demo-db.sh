#!/usr/bin/env bash
# BASKET — drop, recreate, migrate and seed an ISOLATED demonstration database.
#
#   scripts/reset-demo-db.sh                # uses database "basket_demo"
#   DEMO_DB_NAME=basket_pitch_demo scripts/reset-demo-db.sh
#
# Safety: refuses any database whose name does not end in "_demo", so it can
# never touch basket_db (development) or a production database. Connection
# host/user/password are taken from DATABASE_URL in backend/.env.
#
# Then run the app against it:
#   cd backend && DATABASE_URL="<same url>/basket_demo" .venv/bin/uvicorn app.main:app --reload
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
DEMO_DB_NAME="${DEMO_DB_NAME:-basket_demo}"

if [[ "$DEMO_DB_NAME" != *_demo ]]; then
  echo "Refusing: DEMO_DB_NAME must end with _demo (got '$DEMO_DB_NAME')." >&2
  exit 1
fi

BASE_URL="$(grep -E '^DATABASE_URL=' "$BACKEND/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
if [[ -z "$BASE_URL" ]]; then
  echo "DATABASE_URL not found in backend/.env" >&2
  exit 1
fi
ASYNC_URL="${BASE_URL%/*}/$DEMO_DB_NAME"
PG_URL="$(echo "${BASE_URL%/*}/postgres" | sed 's/+asyncpg//')"

echo "Recreating database '$DEMO_DB_NAME'..."
psql "$PG_URL" -v ON_ERROR_STOP=1 -q \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DEMO_DB_NAME' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS \"$DEMO_DB_NAME\";" \
  -c "CREATE DATABASE \"$DEMO_DB_NAME\";"

cd "$BACKEND"
echo "Applying migrations..."
DATABASE_URL="$ASYNC_URL" .venv/bin/alembic upgrade head
echo "Seeding demonstration data..."
DATABASE_URL="$ASYNC_URL" OPENSEARCH_URL="" KAFKA_BOOTSTRAP_SERVERS="" \
  .venv/bin/python -m app.seeds.seed_demo_marketplace

cat <<MSG

Demo database '$DEMO_DB_NAME' is ready.
Accounts (password Basket@123): customer@basket.demo, admin@basket.demo,
retailer1@basket.demo .. retailer4@basket.demo
Start the API against it:
  cd backend && DATABASE_URL="\${DATABASE_URL%/*}/$DEMO_DB_NAME" .venv/bin/uvicorn app.main:app --reload --port 8000
MSG
