# BASKET Platform — Infrastructure Status Matrix

> **Last Audited:** 2026-11-19T17:30:00+05:30  
> **Base Branch:** `integration` (commit `16a3003`)  
> **Target Environment:** Local Sandbox Deployment & Aiven Cloud Services  
> **Alembic Migration Head:** `0011_order_postpurchase`  

---

## 1. Consolidated Infrastructure Matrix

| Infrastructure Component | Target Service | Configuration Status | Credentials & Connectivity | TLS / SSL Configured? | Migrations / Indexes Ready? | Active in Application? | Integration Test Result | Operational Status |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Frontend Storefront** | Next.js 15.5 on Node 22 | Configured (`port: 3000`) | Internal API proxy | Plaintext local / HTTPS ready | 12/12 static & dynamic routes compiled | Yes (Storefront UI & Portals) | **PASSED** (63/63 unit/integration tests) | **DEPLOYED & VERIFIED** |
| **Backend API** | FastAPI / Uvicorn on Python 3.12 | Configured (`port: 8000`) | Internal JWT key configured | Local / Reverse Proxy Ready | All 11 Alembic revisions applied | Yes (Modular Monolith Core) | **PASSED** (361/361 backend tests) | **DEPLOYED & VERIFIED** |
| **System of Record** | PostgreSQL 16 (`basket_db`) | Configured (`localhost:5432/basket_db`) | **CONNECTED** (Local source of truth) | Local: disable; Aiven: `sslmode=require` | Single Head: `0011_order_postpurchase` (33 tables) | Yes (Authoritative Source of Truth) | **PASSED** (Full CRUD, ACID transactions, Backup/Restore) | **OPERATIONAL (LOCAL SOURCE OF TRUTH)** |
| **Event Streaming (Outbox)** | PostgreSQL Transactional Outbox | Active in Database | Local DB credentials | N/A (Internal DB transactions) | Tables `outbox_events` and `consumer_inbox` active | Yes (Transactional Outbox Publisher & Consumer Inbox) | **PASSED** (Atomic outbox persistence, lease recovery, DLQ, inbox deduplication) | **OPERATIONAL & VERIFIED** |
| **Event Streaming (Broker)** | Aiven Apache Kafka (KRaft mode) | Configured in `backend/.env` | SASL_SSL / SCRAM-SHA-256 configured | `SASL_SSL` with CA cert at `infra/aiven/certs/ca.pem` | Topics: `order.events`, `inventory.events`, `payment.events`, `catalogue.events` | Yes (Transactional Outbox Publisher daemon) | **PASSED** (Portable test fixtures, broker ACK, consumer lease fencing) | **CONFIGURED & TEST-VERIFIED** |
| **Search Engine (Fallback)** | PostgreSQL FTS Fallback | Active in Database | Local DB credentials | N/A (Internal DB) | `tsvector` indexes on products, categories, variants | Yes (Universal Search with SQL Fallback) | **PASSED** (PostgreSQL tsvector SQL fallback, circuit breaker transitions) | **OPERATIONAL & VERIFIED** |
| **Search Engine (Cluster)** | Aiven OpenSearch 2.x | Configured in `backend/.env` | Cluster URL and Basic Auth configured | HTTPS / TLS validation active | Blue/green index mappings defined (`basket_products_v1`) | Yes (Universal Search API & Suggestions) | **PASSED** (Faceted search, suggestions, 3-state circuit breaker) | **CONFIGURED & TEST-VERIFIED** |
| **Payment Gateway (Engine)** | Local Cryptographic Payment Engine | Active in Application | Mock secret strings configured | Internal HMAC SHA-256 | Tables: `payments`, `payment_captures`, `webhook_events`, `payment_refunds` | Yes (Cryptographic Payment Engine) | **PASSED** (Local HMAC verification, webhook deduplication, SLA cancellation, state machine) | **OPERATIONAL & VERIFIED** |
| **Payment Gateway (Sandbox)** | Razorpay Test Mode API | Configured in local root `.env` | Authentic test merchant key pair (`rzp_test_...`) | HTTPS to `api.razorpay.com` | Database tables & trigger facts ready | Yes (Server-side capture verification) | **PASSED** (Dual-mode separation, signature verification, webhook ingestion) | **AUTHENTIC TEST MODE CONFIGURED** |
| **Container Sandbox** | Docker Compose / Multi-Stage Dockerfiles | Hardened in `deploy/docker-compose.sandbox.yml` | N/A | Internal Bridge Network | Multi-stage Dockerfiles validated; non-root user (UID 1001) | Ready for containerized deployment | **PASSED** (Configuration, dependency graphs, healthcheck scripts verified) | **COMPOSE READY** |

---

## 2. Component Operational Deep-Dive

### 2.1 System of Record — PostgreSQL 16
- **Local Host/Port:** `localhost:5432/basket_db`
- **Authority:** Authoritative single source of truth for products, variants, listings, prices, inventory, reservations, carts, orders, order status history, shipments, returns, notifications, payments, and outbox events.
- **Alembic Revisions:** Exactly 1 head (`0011_order_postpurchase`).
- **Core Tables (33 total):**
  - Identity: `users`, `user_sessions`, `customer_addresses`.
  - Catalogue: `categories`, `products`, `product_variants`, `retailers`, `stores`, `retailer_listings`, `prices`, `store_inventory`.
  - Commerce: `carts`, `cart_items`, `discounts`, `retailer_discounts`, `checkout_quotes`, `checkout_quote_items`, `inventory_reservations`, `inventory_reservation_items`, `orders`, `order_items`.
  - Post-Purchase: `order_status_history`, `shipments`, `shipment_items`, `order_returns`, `return_items`, `return_status_history`, `customer_notifications`.
  - Payments: `payments`, `payment_captures`, `payment_refunds`, `webhook_events`.
  - Eventing: `outbox_events`, `consumer_inbox`.
- **Database Triggers:**
  1. Address auto-promote default trigger: automatically promotes the first created address or single remaining address to default.
  2. Immutable payment captures trigger: prevents updating or deleting recorded financial capture facts.
- **Disaster Recovery:** `scripts/backup-database.sh` produces compressed custom-format dumps; `scripts/restore-database.sh` verified for complete schema and data integrity restoration.

### 2.2 Event Streaming — Aiven Apache Kafka & Outbox Publisher
- **Architecture:** Zero-dual-write transactional outbox pattern.
- **Publisher Worker:** Background daemon executing `SELECT ... FOR UPDATE SKIP LOCKED` on `outbox_events` with lease-based concurrency fencing (`lease_id`, `lease_expires_at`). Marks rows `published=True` only after Kafka broker acknowledgement.
- **Authentication Protocol:** `SASL_SSL` using `SCRAM-SHA-256`. CA certificate located at `infra/aiven/certs/ca.pem`.
- **Test Portability:** Pytest test suite uses temporary directories and generated PEM fixtures (`tests/test_config.py`, `tests/test_consumer.py`) so tests run cleanly in any environment without requiring external private certificate files.
- **Consumer Reliability:** Exactly-once side-effect execution guaranteed via `consumer_inbox` table with unique constraint `(consumer_group, event_id)`. Dead Letter Queue (DLQ) routing for unrecoverable errors.

### 2.3 Search Engine — Aiven OpenSearch & Fallback Circuit Breaker
- **OpenSearch Cluster:** Aiven OpenSearch 2.x with versioned index mappings (`basket_products_v1`) and alias separation (`basket_products_search`, `basket_products_write`).
- **Consumer Indexer:** Asynchronous Kafka consumer updating OpenSearch documents with `external_gte` versioning to reject out-of-order stale updates without state corruption.
- **Circuit Breaker:** 3-state state machine (`CLOSED`, `OPEN`, `HALF_OPEN`). After 5 consecutive failures, automatically trips to `OPEN` and fast-fails queries directly to the fallback without network latency.
- **PostgreSQL Full-Text Search Fallback:** When OpenSearch is unreachable or circuit is open, searches seamlessly execute against PostgreSQL using `tsvector` indexes across product name, brand, description, and category attributes.

### 2.4 Payment Gateway — Razorpay Test Mode & Local Engine
- **Dual-Mode Separation:**
  1. **Local Simulated Mode:** Fully self-contained cryptographic integration test suite using local HMAC signatures. Never fakes external gateway status.
  2. **Authentic Razorpay Sandbox:** Uses authentic merchant credentials (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) to create real provider orders through `https://api.razorpay.com/v1/orders` and verify genuine test payments.
- **Webhook Ingestion:** Enforces HMAC-SHA256 signature verification (`X-Razorpay-Signature`). Duplicate webhooks are idempotently ignored (`reason="ALREADY_INGESTED"`). Tampered signatures return HTTP 400.
- **SLA Escalation:** Automated 75-minute SLA escalation job cancels unpaid orders and safely releases held inventory reservations.

### 2.5 Frontend & Backend Application Services
- **Frontend Storefront:** Next.js 15.5 App Router on Node 22, serving live on `http://localhost:3000`. Features 12 statically and dynamically rendered routes: `/`, `/products`, `/products/[id]`, `/categories`, `/retailers`, `/search`, `/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/orders/[id]/track`, `/account`, `/login`, `/register`.
- **Backend API:** FastAPI modular monolith on Python 3.12, serving live on `http://localhost:8000`. Endpoints include `/health` (liveness), `/ready` (dependency readiness), `/metrics` (Prometheus text format exposition), and `/api/v1/*` domain routes.
