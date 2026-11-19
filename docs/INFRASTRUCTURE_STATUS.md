# BASKET Platform — Infrastructure Status Matrix

**Last Audited:** 2026-11-19
**Branch:** `feature/sandbox-deployment-production-readiness`
**Target Environment:** Local Sandbox Deployment & External Staging Rehearsal

---

## 1. Consolidated Infrastructure Matrix

| Infrastructure Component | Target Service | Configuration Status | Credentials Available? | Live Connectivity | TLS / SSL Configured? | Migrations / Indexes Ready? | Active in Application? | Integration Test Result | Current Status |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Frontend Storefront** | Next.js 15.5 on Node 22 | Configured (`port: 3000`) | N/A (Client) | **ONLINE** (HTTP 200) | Development Plaintext / Proxy Ready | Compiled (11/11 pages static & dynamic) | Yes (Storefront UI) | **PASSED** (60/60 unit/integration tests) | **DEPLOYED & VERIFIED** |
| **Backend API** | FastAPI / Uvicorn on Python 3.12 | Configured (`port: 8000`) | Internal Key Configured | **ONLINE** (HTTP 200) | Local / Reverse Proxy Ready | All 10 Alembic revisions applied | Yes (System Core) | **PASSED** (338/338 backend tests) | **DEPLOYED & VERIFIED** |
| **System of Record** | PostgreSQL 16 (Local Sandbox / Aiven) | Configured (`localhost:5432/basket_db`) | Local credentials active; Aiven unconfigured | **CONNECTED** (Pool: 10/5) | Local: disable; Aiven: `require` | Single Head: `0010_consumer_inbox` (29 tables) | Yes (Source of Truth) | **PASSED** (Full CRUD, ACID transactions, Backup/Restore) | **LOCAL VERIFIED / AIVEN READY** |
| **Event Streaming (Outbox)** | PostgreSQL Transactional Outbox | Active in Database | Local DB credentials | **OPERATIONAL** | N/A (Local Database) | Table `outbox_events` and `consumer_inbox` active | Yes (Transactional Outbox Publisher & Consumer Inbox) | **PASSED** (Outbox persistence, lease recovery, DLQ, inbox deduplication) | **LOCAL VERIFIED** |
| **Event Streaming (Broker)** | Apache Kafka (KRaft mode / Aiven) | Template ready in `.env.example` | Unset (`KAFKA_BOOTSTRAP_SERVERS` empty) | **UNCONNECTED** | SSL mTLS ready (`ca.pem`, `service.cert`, `service.key`) | Topics defined: `order.events`, `inventory.events`, `payment.events` | Inactive (Pending external broker) | **BLOCKED — CREDENTIALS REQUIRED** | **CLUSTER UNCONFIGURED** |
| **Search Engine (Fallback)** | PostgreSQL FTS Fallback | Active in Database | Local DB credentials | **OPERATIONAL** | N/A (Local Database) | `tsvector` indexes on products and variants | Yes (Universal Search with SQL Fallback) | **PASSED** (PostgreSQL tsvector SQL fallback, circuit breaker transitions) | **LOCAL VERIFIED** |
| **Search Engine (Cluster)** | OpenSearch 2.13 (Aiven / Local) | Template ready in `.env.example` | Unset (`OPENSEARCH_URL` empty) | **UNCONNECTED** | HTTPS / TLS validation ready | Blue/green index mappings defined (`basket_products_v1`) | Inactive (Pending external cluster) | **BLOCKED — CREDENTIALS REQUIRED** | **CLUSTER UNCONFIGURED** |
| **Payment Gateway (Engine)** | Local Cryptographic Payment Engine | Active in Application | Mock secret strings configured | **OPERATIONAL** | Internal HMAC SHA-256 | Database tables: `payments`, `payment_captures`, `webhook_events`, `refunds` | Yes (Cryptographic Payment Engine) | **PASSED** (Local HMAC verification, webhook deduplication, SLA cancellation, state machine) | **LOCAL VERIFIED** |
| **Payment Gateway (Sandbox)** | Razorpay Sandbox API | Template ready in `.env.example` | Unset (Requires `rzp_test_...` merchant keys) | **UNCONNECTED** | HTTPS to `api.razorpay.com` | Database tables ready | Inactive (Pending authentic test keys) | **BLOCKED — CREDENTIALS REQUIRED** | **CREDENTIALS PENDING** |
| **Container Sandbox** | Docker Compose / Multi-Stage Dockerfiles | Hardened in `deploy/docker-compose.sandbox.yml` | N/A | Host machine lacks Docker daemon | N/A (Internal Bridge Network) | Multi-stage Dockerfiles validated; non-root user (UID 1001) | Ready for containerized deployment | **PASSED** (Configuration, dependency graphs, healthcheck scripts verified) | **COMPOSE READY / HOST CLI MISSING** |

---

## 2. Service-by-Service Technical Audit

### 2.1 Frontend Storefront (Next.js 15)
- **Runtime:** Node.js 22.x
- **Build Outcome:** Built production bundle in 1.45s with Next.js 15.5.
- **Port:** Local `http://localhost:3000`, returning HTTP 200 with complete HTML hydration and stylesheet preloading.
- **Storefront Client Tests:** All 60 client-side integration tests passing across auth, cart, quotes, reservations, orders, and payments.

### 2.2 Backend API (FastAPI)
- **Runtime:** Python 3.12.16 with Uvicorn worker process.
- **Endpoints:**
  - `GET /health`: Returns `{"status":"ok","service":"basket-backend","environment":"development"}`.
  - `GET /ready`: Returns `{"status":"ready","service":"basket-backend","checks":{"database":{"status":"connected"}}}`.
  - `GET /metrics`: Prometheus text format exposition with request duration histograms and counters.
- **Lifespan Manager:** Handles orderly database engine initialization and graceful teardown of background consumers without blocking API bootstrap.

### 2.3 PostgreSQL Database
- **Host/Port:** `localhost:5432/basket_db`
- **Schema Revision:** `0010_consumer_inbox` (single Alembic head).
- **Core Entities Verified:** 29 tables encompassing users, user sessions, addresses, categories, products, variants, listings, store inventory, carts, quotes, reservations, orders, order history, payments, payment captures, payment refunds, webhook events, outbox events, and consumer inbox.
- **Disaster Recovery:** `scripts/backup-database.sh` generates compressed custom-format dumps (5.8MB); `scripts/restore-database.sh` successfully restored to a temporary disposable database (`basket_restore_test_db`) with full schema and row integrity verified.

### 2.4 Apache Kafka
- **Resilience Mechanism:** When `KAFKA_BOOTSTRAP_SERVERS` is empty or unreachable, the transactional outbox pattern guarantees zero data loss:
  1. Business mutations and `outbox_events` are committed atomically in PostgreSQL.
  2. The background publisher uses `SELECT ... FOR UPDATE SKIP LOCKED` with durable leases.
  3. Consumer inbox records idempotently protect against duplicate deliveries using `(consumer_group, event_id)` unique constraints.
  4. Failed deliveries transition through exponential backoff to a Dead Letter Queue (DLQ).

### 2.5 OpenSearch
- **Resilience Mechanism:** When `OPENSEARCH_URL` is empty or cluster connection fails:
  1. The `SearchCircuitBreaker` fast-fails after reaching the consecutive failure threshold (state transitions to `OPEN`).
  2. Search queries automatically route to `_search_postgres_fallback()`, utilizing PostgreSQL `tsvector` full-text search across product name, brand, description, and category attributes.
  3. Facet computations are omitted during fallback to protect database CPU.

### 2.6 Razorpay Payment Gateway (Dual-Mode Architecture)
- **Local Payment & Webhook Engine (VERIFIED):**
  1. Webhook ingestion enforces strict cryptographic HMAC-SHA256 signature verification (`X-Razorpay-Signature`).
  2. Duplicate webhooks are idempotently deduplicated (`status="ignored", reason="ALREADY_INGESTED"`).
  3. Tampered or forged signatures return HTTP 400 (`INVALID_SIGNATURE`).
  4. Capture facts are immutable in `payment_captures` (guaranteed by database triggers).
  5. SLA escalation job automatically cancels orders and releases reservations if unpaid after 75 minutes.
  6. Domain events are persisted atomically to `outbox_events`.
- **Genuine Razorpay Sandbox API (BLOCKED — CREDENTIALS REQUIRED):**
  1. In the absence of live merchant test keys (`rzp_test_...`), external API calls fail closed (`GATEWAY_UNAVAILABLE` 502 or `PAYMENT_CREATION_AMBIGUOUS` 504), preventing unauthorized mock orders from masquerading as authentic payments.
  2. The test suite strictly refuses to mutate database records, forge provider order IDs, or simulate fake captures to bypass external gateway verification. Real provider checkout requires authentic merchant credentials.

---

## 3. Outstanding Blockers & Owner Action Required

| Service | Blocker Description | Exact Owner Action Required |
|:---|:---|:---|
| **Aiven PostgreSQL** | External cloud database URL not injected | Populate `DATABASE_URL` in `.env` with Aiven PostgreSQL connection URI (`?ssl=require`). |
| **Aiven Kafka** | External Kafka broker credentials and TLS certificates not supplied | Set `KAFKA_BOOTSTRAP_SERVERS` and place `ca.pem`, `service.cert`, and `service.key` in `infra/aiven/certs/`. |
| **Aiven OpenSearch** | External OpenSearch endpoint not supplied | Set `OPENSEARCH_URL`, `OPENSEARCH_USERNAME`, and `OPENSEARCH_PASSWORD` in `.env`. |
| **Razorpay Sandbox** | Authentic test merchant key pair not provided | Supply valid `RAZORPAY_KEY_ID` (`rzp_test_...`), `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` in `.env`. |
| **Docker Daemon** | Host environment lacks `docker` engine | Install Docker Desktop or container CLI on the host to run `docker compose -f deploy/docker-compose.sandbox.yml up -d`. |
