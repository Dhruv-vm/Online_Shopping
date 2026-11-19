# BASKET Platform — Sandbox Operations & Deployment Runbook

This runbook documents operational procedures for deploying, maintaining, monitoring, and troubleshooting the BASKET e-commerce platform in sandbox and staging environments.

---

## 1. Stack Architecture & Deployment Modes

BASKET supports two deployment modes:
1. **Host-Native Deployment (Current Sandbox):** Runs PostgreSQL 16 on `localhost:5432`, FastAPI / Uvicorn on `localhost:8000`, and Next.js 15 on `localhost:3000`.
2. **Containerized Deployment (Docker Compose):** Uses `deploy/docker-compose.sandbox.yml` with isolated bridge networking and health-checked service dependencies.

---

## 2. Service Management Commands

### 2.1 Host-Native Deployment

#### Start Services
```bash
# 1. Start PostgreSQL (Homebrew service on macOS)
brew services start postgresql@16

# 2. Start Backend API
cd backend
source .venv/bin/activate
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

# 3. Start Frontend Storefront
cd frontend
npm start  # or npm run dev for live reloading
```

#### Stop Services
```bash
# Terminate running servers
pkill -f "uvicorn app.main:create_app"
pkill -f "next start"
```

#### Restart Services
```bash
pkill -f "uvicorn app.main:create_app"
cd backend && .venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 &
```

---

### 2.2 Docker Compose Deployment

#### Build and Start All Containers
```bash
# Ensure valid environment variables are set in .env
docker compose -f deploy/docker-compose.sandbox.yml up --build -d
```

#### Check Container Status and Health
```bash
docker compose -f deploy/docker-compose.sandbox.yml ps
```

#### View Live Logs
```bash
# Follow logs for all services
docker compose -f deploy/docker-compose.sandbox.yml logs -f

# Follow specific service logs
docker compose -f deploy/docker-compose.sandbox.yml logs -f backend
docker compose -f deploy/docker-compose.sandbox.yml logs -f frontend
```

#### Stop Containers
```bash
docker compose -f deploy/docker-compose.sandbox.yml down
```

---

## 3. Health & Readiness Verification

| Endpoint | Method | Expected Output | Purpose |
|:---|:---:|:---|:---|
| `http://localhost:8000/health` | `GET` | `{"status":"ok","service":"basket-backend"}` | Liveness probe |
| `http://localhost:8000/ready` | `GET` | `{"status":"ready","checks":{"database":{"status":"connected"}}}` | Readiness probe across DB, Kafka, OpenSearch |
| `http://localhost:8000/metrics` | `GET` | Prometheus exposition text | Telemetry & request latencies |
| `http://localhost:3000` | `GET` | HTTP 200 HTML content | Storefront availability |

Verification script:
```bash
curl -f -s http://localhost:8000/health | jq .
curl -f -s http://localhost:8000/ready | jq .
curl -f -sI http://localhost:3000 | head -n 5
```

---

## 4. Database Migrations

### 4.1 Check Current Revision Status
```bash
cd backend
.venv/bin/alembic current
```

### 4.2 Verify Single Migration Head
```bash
cd backend
.venv/bin/alembic heads
```
*Requirement:* Must return exactly one head (`0010_consumer_inbox`). Multiple heads indicate an unmerged migration branch.

### 4.3 Apply Migrations
```bash
cd backend
.venv/bin/alembic upgrade head
```

---

## 5. Backup & Disaster Recovery

### 5.1 Execute Database Backup
```bash
./scripts/backup-database.sh
```
- Creates a timestamped PostgreSQL custom-format dump in `./backups/basket_db_<TIMESTAMP>.dump`.
- Excludes backups from Git via `.gitignore`.

### 5.2 Test Restore on Disposable Database
```bash
# Create disposable target
createdb -h localhost -U dhruv basket_restore_test_db

# Execute restore script
DB_NAME=basket_restore_test_db ./scripts/restore-database.sh ./backups/basket_db_<TIMESTAMP>.dump

# Verify tables and clean up
psql -h localhost -U dhruv -d basket_restore_test_db -c '\dt'
dropdb -h localhost -U dhruv basket_restore_test_db
```

---

## 6. Secret Rotation Procedure

When rotating secrets:

1. **JWT `SECRET_KEY`:**
   - Generate a new 32+ character high-entropy key: `openssl rand -hex 32`.
   - Update `SECRET_KEY` in `backend/.env`.
   - Note: Existing user sessions will be required to re-authenticate on token expiry.
2. **Internal Service Key (`INTERNAL_SERVICE_KEY`):**
   - Generate new key: `openssl rand -hex 32`.
   - Update in both `backend/.env` and background cron/reconciliation worker environment.
3. **Razorpay Webhook Secret (`RAZORPAY_WEBHOOK_SECRET`):**
   - Generate secret in Razorpay Dashboard -> Webhooks.
   - Update `RAZORPAY_WEBHOOK_SECRET` in `backend/.env`.
   - Restart backend server.
4. **Database Credentials:**
   - Update `DATABASE_URL` in `backend/.env` with new password.
   - Restart application to re-initialize SQLAlchemy connection pool.

---

## 7. Troubleshooting & Failure Recovery

### 7.1 Kafka Unavailability
- **Symptom:** Logs show `Background consumer could not start at lifespan startup` or Kafka broker disconnects.
- **System Behavior:** API continues serving traffic without crashing. All domain events remain persisted safely in the `outbox_events` table in PostgreSQL.
- **Recovery:** Once Kafka broker is reachable, restart the background outbox publisher:
  ```bash
  cd backend
  .venv/bin/python -m app.core.events.publisher
  ```

### 7.2 OpenSearch Outage / Circuit Breaker OPEN
- **Symptom:** Search logs display `CircuitBreakerOpenError` or OpenSearch connection dropped.
- **System Behavior:** Search automatically routes to `_search_postgres_fallback()` using PostgreSQL full-text search. The circuit breaker probes the cluster periodically and automatically closes when OpenSearch recovers.
- **Manual Verification:**
  ```bash
  curl -s "http://localhost:8000/api/v1/search?q=Sony&force_fallback=true" | jq .engine
  # Returns: "postgres_fallback"
  ```

### 7.3 Payment Gateway Ambiguity (504 Timeout)
- **Symptom:** Payment initiation returns HTTP 504 `PAYMENT_CREATION_AMBIGUOUS`.
- **System Behavior:** The attempt is recorded in `payments` with `CREATION_AMBIGUOUS` status to prevent duplicate charges.
- **Resolution:** Periodic background SLA worker resolves pending attempts via Razorpay GET order query:
  ```bash
  curl -X POST "http://localhost:8000/api/v1/internal/payments/sla-escalation" \
    -H "X-Internal-Service-Key: <your_internal_service_key>"
  ```

---

## 8. End-to-End Sandbox Verification & Payment Testing Modes

The platform includes an automated end-to-end verification script: `scripts/e2e_sandbox_journey.py`.

### 8.1 Dual Payment Verification Modes

1. **Local Simulated Payment & Webhook Integration (Default / No Credentials Required):**
   - Tests local HMAC-SHA256 signature calculation and validation.
   - Tests webhook ingestion (`POST /api/v1/payments/webhook`) with local test secrets.
   - Tests duplicate event deduplication (`ALREADY_INGESTED`).
   - Tests tampered signature rejection (HTTP 400 `INVALID_SIGNATURE`).
   - Tests local background webhook processor (`WebhookService`).
   - Tests transactional outbox table persistence.
   - **Result:** Fully runnable and verified in local sandbox without any external accounts.

2. **Genuine Razorpay Sandbox Payment (Requires Authentic Test Merchant Credentials):**
   - Requires setting `RAZORPAY_KEY_ID` (starting with `rzp_test_`), `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` in `backend/.env`.
   - Calls the live Razorpay API endpoint `https://api.razorpay.com/v1/orders`.
   - Verifies authentic provider signatures and capture webhooks.
   - **Crucial Policy:** If credentials are not provisioned, the test suite strictly marks the test **`BLOCKED — CREDENTIALS REQUIRED`**. It **never** fabricates fake provider order IDs or modifies database records to fake a successful provider transaction.

### 8.2 Running the E2E Verification Script

```bash
# Standard local sandbox run (allows BLOCKED external services):
cd Online_Shopping
backend/.venv/bin/python scripts/e2e_sandbox_journey.py

# Strict mode for staging/production (fails if any external service is BLOCKED):
backend/.venv/bin/python scripts/e2e_sandbox_journey.py --require-external
```
