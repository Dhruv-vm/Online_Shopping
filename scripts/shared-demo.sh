#!/bin/zsh
# BASKET shared two-laptop demo control.
#   scripts/shared-demo.sh up        start Kafka + OpenSearch (Docker), the API and the frontend
#   scripts/shared-demo.sh down      stop the API and frontend, stop the containers (data kept)
#   scripts/shared-demo.sh status    show what is running and the URLs
#   scripts/shared-demo.sh reset-db  rebuild basket_shared_demo from the demo seed (asks first)
#   scripts/shared-demo.sh tunnel    expose the frontend through a Cloudflare quick tunnel
#   scripts/shared-demo.sh urls      print the URLs for Laptop A / Laptop B
#
# One shared marketplace: both laptops use this Mac's frontend (port 3100), which
# proxies the API (127.0.0.1:8100). The API uses database basket_shared_demo,
# Kafka (outbox, OUTBOX_DISPATCH=kafka) and a local OpenSearch. Nothing but the
# frontend port is reachable from the network. basket_db is never used.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.shared-demo"
COMPOSE=(docker compose -f "$ROOT/deploy/docker-compose.shared-demo.yml")
DB_NAME="basket_shared_demo"
API_PORT=8100
WEB_PORT=3100
mkdir -p "$STATE"

[[ "$DB_NAME" == *_demo ]] || { echo "Refusing: demo database must end in _demo"; exit 2; }

env_url="$(grep -E '^DATABASE_URL=' "$ROOT/backend/.env" "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
DB_URL="${env_url%/*}/${DB_NAME}"
[[ "$DB_URL" == *"/$DB_NAME"* ]] || { echo "Could not build the demo DATABASE_URL"; exit 2; }

lan_ip() { ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<this-mac-ip>"; }

api_env() {
  export DATABASE_URL="$DB_URL"
  export OUTBOX_DISPATCH=kafka
  export KAFKA_BOOTSTRAP_SERVERS=localhost:9094 KAFKA_SECURITY_PROTOCOL=PLAINTEXT
  export KAFKA_SASL_USERNAME="" KAFKA_SASL_PASSWORD="" KAFKA_SSL_CA_LOCATION=""
  export KAFKA_SSL_CERTIFICATE_LOCATION="" KAFKA_SSL_KEY_LOCATION=""
  export OPENSEARCH_URL=http://localhost:9201 OPENSEARCH_USERNAME="" OPENSEARCH_PASSWORD=""
  export OPENSEARCH_VERIFY_CERTS=false
  export MEDIA_PUBLIC_BASE_URL=/media
  export DEBUG=false SQL_ECHO=false
}

wait_http() { for i in {1..90}; do curl -fs -o /dev/null "$1" && return 0; sleep 2; done; return 1; }

start_api() {
  [[ -f "$STATE/api.pid" ]] && kill -0 "$(cat "$STATE/api.pid")" 2>/dev/null && { echo "API already running"; return; }
  ( cd "$ROOT/backend" && api_env && nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $API_PORT \
      > "$STATE/api.log" 2>&1 & echo $! > "$STATE/api.pid" )
  wait_http "http://127.0.0.1:$API_PORT/health" && echo "API ready on 127.0.0.1:$API_PORT" || { echo "API failed; see $STATE/api.log"; exit 1; }
}

start_web() {
  [[ -f "$STATE/web.pid" ]] && kill -0 "$(cat "$STATE/web.pid")" 2>/dev/null && { echo "Frontend already running"; return; }
  cd "$ROOT/frontend"
  export NEXT_PUBLIC_API_URL=same-origin BASKET_API_PROXY_TARGET="http://127.0.0.1:$API_PORT" NEXT_DIST_DIR=.next-shared
  if [[ ! -f .next-shared/BUILD_ID || "${REBUILD:-0}" == 1 ]]; then
    echo "Building the frontend (production build, separate .next-shared directory)..."
    ./node_modules/.bin/next build > "$STATE/web-build.log" 2>&1 || { echo "Build failed; see $STATE/web-build.log"; exit 1; }
  fi
  nohup ./node_modules/.bin/next start -H 0.0.0.0 -p $WEB_PORT > "$STATE/web.log" 2>&1 &
  echo $! > "$STATE/web.pid"
  wait_http "http://127.0.0.1:$WEB_PORT/" && echo "Frontend ready on port $WEB_PORT" || { echo "Frontend failed; see $STATE/web.log"; exit 1; }
}

stop_pid() {
  # Always succeeds (the script runs with `set -e`), even if nothing was running.
  if [[ -f "$STATE/$1.pid" ]]; then
    kill "$(cat "$STATE/$1.pid")" 2>/dev/null || true
    rm -f "$STATE/$1.pid"
  fi
  return 0
}

urls() {
  echo "Laptop A (customer) and Laptop B (retailer) open the SAME address:"
  echo "  Same Wi-Fi:  http://$(lan_ip):$WEB_PORT"
  [[ -f "$STATE/tunnel.url" ]] && echo "  Tunnel:      $(cat "$STATE/tunnel.url")"
  echo "Accounts (password Basket@123): customer@basket.demo · retailer1@basket.demo … retailer4@basket.demo · admin@basket.demo"
}

case "${1:-status}" in
  up)
    "${COMPOSE[@]}" up -d --wait
    if ! /opt/homebrew/bin/psql "${DB_URL/+asyncpg/}" -Atc "select 1" >/dev/null 2>&1; then
      echo "Creating $DB_NAME from the demo seed..."
      DEMO_DB_NAME=$DB_NAME "$ROOT/scripts/reset-demo-db.sh" > "$STATE/reset.log" 2>&1
    fi
    start_api; start_web; urls ;;
  down)
    stop_pid tunnel; stop_pid web; stop_pid api; rm -f "$STATE/tunnel.url"
    "${COMPOSE[@]}" stop; echo "Stopped (data kept in Docker volumes and $DB_NAME)." ;;
  status)
    "${COMPOSE[@]}" ps --format 'table {{.Service}}\t{{.Status}}'
    for p in api web tunnel; do [[ -f "$STATE/$p.pid" ]] && kill -0 "$(cat "$STATE/$p.pid")" 2>/dev/null && echo "$p: running" || echo "$p: stopped"; done
    curl -fs "http://127.0.0.1:$API_PORT/ready" 2>/dev/null | head -c 600; echo; urls ;;
  reset-db)
    read "?Rebuild $DB_NAME (all demo activity is lost)? [y/N] " ok; [[ "$ok" == y ]] || exit 0
    stop_pid api; DEMO_DB_NAME=$DB_NAME "$ROOT/scripts/reset-demo-db.sh"; echo "Run: scripts/shared-demo.sh up" ;;
  tunnel)
    command -v cloudflared >/dev/null || { echo "cloudflared not installed (brew install cloudflared)"; exit 1; }
    nohup cloudflared tunnel --no-autoupdate --url "http://localhost:$WEB_PORT" > "$STATE/tunnel.log" 2>&1 &
    echo $! > "$STATE/tunnel.pid"
    for i in {1..30}; do u=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$STATE/tunnel.log" | head -1); [[ -n "$u" ]] && break; sleep 1; done
    [[ -n "${u:-}" ]] && { echo "$u" > "$STATE/tunnel.url"; urls; } || { echo "Tunnel did not start; see $STATE/tunnel.log"; exit 1; } ;;
  restart)
    # Rebuilds the frontend so code changes are served; data is kept.
    "$0" down; REBUILD=1 "$0" up ;;
  urls) urls ;;
  *) echo "usage: $0 up|down|restart|status|reset-db|tunnel|urls"; exit 2 ;;
esac
