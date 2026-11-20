# BASKET — Comprehensive Backend Architecture & Module Audit

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Environment:** FastAPI 0.115.11 | Python 3.12.14 | SQLAlchemy 2.0.38 (Async)  
> **Audit Date:** 2026-11-20  
> **Author:** Antigravity Architecture & Reliability Audit Team  

---

## P3. Phase 3 Implementation & Comprehensive Final Audit — 2026-11-20

> Branch `feature/phase-3-advanced-marketplace` (local; based on `audit/stabilisation-and-repair` @ `95a5de1`). Supersedes earlier sections where they conflict.

### P3.1 New modules
`demand`, `community`, `exchange`, `negotiation`, `auctions`, `price_intel`, `sale_stream`, `i18n`, `vision` under `backend/app/modules/`, plus shared `pricing/awards.py` (`PriceAward`), `cart/integration.py`, `core/events/marketplace_events.py`, `core/notify.py`, `core/pincode.py`, `core/search/versioning.py`. Migrations `0022`–`0030` (all reversible; downgrade to `0021` and re-upgrade verified). 53 new endpoints (201 operations total).

### P3.2 Final audit — results by area

| # | Area | Result | Evidence / notes |
| :--- | :--- | :--- | :--- |
| 1 | Phase 1 functionality | ✅ | All Phase 1 tests pass; one test adjusted to fulfil only paid orders (audit rule). |
| 2 | Phase 2 (missions, substitutes, intent, passport) | ✅ | All pass; mission budget test was disturbed by Phase 3 fixtures → fixtures isolated. |
| 3 | Phase 3 features | ✅ (3I OCR provider not configured) | 45 feature tests; see TEST_REPORT.md. |
| 4–6 | Admin / retailer / customer workflows | ✅ API-level | Browser E2E not executed (no E2E framework in repo). |
| 7 | Database consistency | ✅ | Empty→head and down/up verified; FK/CHECK/unique constraints on all new tables; partial unique indexes for open demand pools and negotiation-rule scope; no Phase 3 `alembic check` drift. |
| 8 | API contracts | ✅ | Route walk = 201 operations; all documented in API_INVENTORY.md and FRONTEND_INTEGRATION_GUIDE.md. |
| 9 | AuthN / RBAC | ✅ | Every Phase 3 mutation: role dependency + CSRF; ownership enforced in services (404 for foreign resources). Retailers/admins cannot act as customers in customer flows (403). |
| 10 | Razorpay | ✅ (mocked) | Payment suite unchanged and green; special prices reach Razorpay only via server quotes/orders. |
| 11 | Inventory & orders | ✅ | Awards consumed atomically with order creation; stock checks at join/bid/accept; reservations unchanged. |
| 12 | Kafka | ⚠️ code-verified, live broker unavailable | New topic `basket.events.marketplace` (must be created in Aiven). Aiven broker DNS does not resolve. |
| 13 | OpenSearch | ✅ live | Live Aiven probe passed (projection, versioning, search, delete). **Fixed**: unconfigured environments queried an empty mock index (0 results). |
| 14 | Media | ⚠️ unchanged | URL-only (validated). OCR upload uses validated base64 JSON. Object storage still missing (DISC-01). |
| 15 | Frontend/backend integration | ✅ | Typed client + 12 tests; 48 routes build. |
| 16 | Security | ✅ | See P3.3. |
| 17 | Performance & reliability | ✅ with notes | Suite 87.7 s; new indexes on all hot lookups; background jobs bounded (≤50–200 rows/run). Search fallback per-request aggregates are fine at current catalogue size (~800 products) but should move to OpenSearch-only at scale. |
| 18 | Error handling | ✅ | Uniform `{error:{code,message,details}}`; zero-result demand capture isolated in a savepoint so it can never break search. |
| 19 | Test coverage | ✅ | 513 backend (+46 vs audit), 112 frontend (+12). |
| 20 | Documentation | ✅ | 10 documents updated/created; false claims corrected (HMAC quotes, vitest, tsvector, test isolation). |

### P3.3 Security review of Phase 3
* Floors and competing bids are never exposed (negotiation floor hidden; retailers only see best price, not who bid).
* All prices server-computed; bids capped at the bidder's list price; awards single-use, customer-bound, time-limited.
* Demand manipulation: unique-shopper counts use authenticated customers only; retailers/admins cannot cast signals.
* Image intake: type allow-list + magic-byte check + 5 MB cap; OCR provider never fabricates output.
* Live-infrastructure isolation: test suite blanks Kafka/OpenSearch unless explicitly opted in.

### P3.4 Incident during Phase 3 testing (resolved)
The repository-root `.env` configures live Aiven OpenSearch/Kafka. Early Phase 3 feature test runs did not blank these, and best-effort synchronous search sync wrote **2 test product documents** to the live `basket_products_v1` index. They were identified precisely (product ids existing only in the scratch test DB) and deleted; a guard in `tests/conftest.py` now prevents recurrence. No Kafka messages were produced (broker unreachable; publisher not started in tests).

### P3.5 Correction
The platform has **no HMAC-signed quotes** (earlier docs claimed “HMAC-SHA256 quotes”). Quotes are server-persisted and referenced by id with ownership checks, which is the actual integrity mechanism.

---


## 0. Stabilisation Audit — 2026-11-20 (independently verified)

> Branch `audit/stabilisation-and-repair` (from `feature/phase-2d-product-passport` @ `026f801`).
> Everything below was verified against source code and executed tests. Where this
> section conflicts with older sections of this document, **this section wins**.

### 0.1 Corrections to earlier claims in this document

| Earlier claim | Verified reality |
| :--- | :--- |
| Tests run on "SQLite async in-memory simulation, zero mutation of production records" | Tests run against whatever `DATABASE_URL` points to (PostgreSQL). The autouse fixture in `tests/conftest.py` **rewrites `store_inventory` quantities** after every test and may seed data. Always run tests against a dedicated database (see §0.6). |
| PostgreSQL fallback uses `tsvector` full-text search | Fallback uses `ILIKE` token matching. It is now escaped and filters in SQL (§0.3). |
| `alembic check` passes | It failed before this audit (model/migration drift). Two missing indexes fixed in `0021`; cosmetic drift remains (§0.5). |
| "Kafka & OpenSearch operational with graceful fallbacks" | The outbox publisher was **never started** and **no catalogue/inventory events were ever produced**; search stock went stale after every sale. Fixed (§0.2). |
| DISC-02 (no Razorpay production guard) open | Already implemented in `core/config.py` validators (live-key prefix, secrets, internal key length). Closed. |
| Order/return/refund endpoints secured by RBAC | Shipment and return-status endpoints were **unauthenticated**; refunds were **customer-callable**. Fixed (§0.1a). |

### 0.1a Security findings (all fixed, with regression tests)

| ID | Severity | Finding | Fix |
| :--- | :---: | :--- | :--- |
| AUD-SEC-01 | Critical | `POST /orders/{id}/shipments`, `PATCH /orders/{id}/shipments/{sid}`, `PATCH /returns/{id}/status` had no authentication. Anyone could mark orders delivered, move returns to `REFUNDED` (real refund) or repeatedly to `INSPECTED` with restock (unbounded stock inflation). | `require_admin_or_internal_service` dependency (admin JWT + CSRF, or `X-Internal-Service-Key`). |
| AUD-SEC-02 | Critical | Customers could call `POST /orders/{id}/refunds` for the full amount on any order, including delivered ones. | Endpoint is admin/internal only; customer refunds go through cancel/returns. |
| AUD-SEC-03 | High | No state machine for returns/shipments: transitions could be skipped or replayed (double refund/restock). Failed refunds were still reported `REFUNDED`. | `RETURN_STATUS_TRANSITIONS`, `SHIPMENT_STATUS_TRANSITIONS`; failed refund ⇒ `REFUND_PENDING`; order only `DELIVERED` when all shipments delivered; history `from_status` bug fixed. |
| AUD-SEC-04 | High | Retailers could fulfil `PENDING_PAYMENT` (unpaid) orders; retailer cancellation neither restocked nor refunded; order row not locked. | Paid-only fulfilment, `SELECT … FOR UPDATE`, restock + refund on cancel (delivery fee refunded when whole order cancelled), dispatched items cannot be cancelled. |
| AUD-SEC-05 | Medium | `X-Forwarded-For` trusted unconditionally ⇒ login rate-limit bypass via spoofed IPs. | Honoured only when `TRUSTED_PROXY_COUNT > 0`. |
| AUD-SEC-06 | Medium | CSRF missing on retailer/admin/passport/orders/payments/reservations/quotes mutations; origin check used substring match (`localhost.evil.com` passed). | Router-level `verify_csrf_token` (safe methods exempt), exact hostname match, localhost only outside production. Frontend already sends `X-CSRF-Token`. |
| AUD-SEC-07 | Low | Session revocation check did not verify session owner; deleted user returned 404. | Session must belong to token subject; 401. |
| AUD-SEC-08 | Medium | Image URLs accepted `javascript:` / `data:` / relative values. | `core/validation.validate_media_url` on admin product/category and retailer custom-product images. |

### 0.2 Kafka / transactional outbox

| Aspect | Status | Evidence |
| :--- | :--- | :--- |
| Producer config (acks, TLS/SASL, retries) | Verified by code review | `core/events/kafka.py` |
| Outbox claim (`FOR UPDATE SKIP LOCKED`), leases, lease-expiry recovery, backoff, terminal `FAILED` | Verified (real PostgreSQL tests) | `tests/test_outbox_publisher.py` |
| **Publisher actually running** | **Was missing → fixed** | `core/background.py` starts `OutboxPublisherWorker` from lifespan; reconnects with exponential backoff (5 s → 300 s) |
| **Catalogue / inventory events produced** | **Was missing → fixed** | `core/events/catalogue_events.py`; emitted on reserve, release, confirm, restock, retailer/admin catalogue changes |
| Consumer inbox idempotency, offset-after-commit, DLQ, poison messages | Verified (tests) | `tests/test_consumer.py` |
| Duplicate delivery absorbed end-to-end | Verified (new test) | `tests/test_audit_event_pipeline.py` |
| Kafka unavailable ⇒ events stay `PENDING` with backoff, API keeps serving | Verified (new test) | same |
| Readiness reports real publisher state + outbox backlog | Fixed | `GET /ready` → `checks.kafka.{status,outbox_pending,outbox_failed}` |
| **Live broker integration** | **NOT VERIFIED** | No Kafka/Docker on the audit machine. Run `deploy/docker-compose.sandbox.yml` before release. |

Per-aggregate ordering: events are published in `next_attempt_at, created_at` order per batch; a retried event can be overtaken by a later one. This is safe for the product projection (documents are rebuilt from PostgreSQL and versioned by snapshot time) and for order projections (consumer enforces monotonic `aggregate_version`).

### 0.3 OpenSearch

| Aspect | Status |
| :--- | :--- |
| Index/alias management, mappings, blue/green helpers | Verified by code review + mock tests |
| **Versioning bug** | Documents were written with the *triggering aggregate's* version and `external_gte`; inventory/listing/product counters are unrelated, so valid updates were rejected (409) and silently dropped. **Fixed:** version = DB snapshot time (`core/search/versioning.py`) in consumer, `sync_product` and `reconcile_from_database`. |
| Delete failures | Were swallowed (stale products stayed searchable). Now re-raised for retry; 404/409 treated as done. |
| Inactive variants | Were contributing prices/stock to documents. Now excluded. |
| PostgreSQL fallback | Price/stock filters applied in Python after pagination (short pages, wrong `total`), price sorts ignored, `%`/`_` acted as wildcards, unpriced products matched price filters. **All fixed in SQL.** |
| **Live cluster integration** | **NOT VERIFIED** (no cluster available). |

### 0.4 Background jobs (new: `core/background.py`)

| Job | Interval (setting) | Multi-replica safety |
| :--- | :--- | :--- |
| Outbox publisher | continuous | SKIP LOCKED + leases |
| Expired reservation release | `RESERVATION_CLEANUP_INTERVAL_SECONDS` (60) | one txn per reservation, row locks |
| Payment reconciliation | `PAYMENT_RECONCILE_INTERVAL_SECONDS` (120) | webhook leases |
| 75-min unpaid SLA escalation | `PAYMENT_SLA_ESCALATION_INTERVAL_SECONDS` (300) | existing job semantics |

Disable with `BACKGROUND_WORKERS_ENABLED=false` if you run dedicated worker processes. Before this audit none of these ran, so **abandoned checkouts held `reserved_quantity` indefinitely**.

### 0.5 Database

* Migrations `0001→0021` apply cleanly from empty on PostgreSQL 16; `0021` verified upgrade → downgrade → upgrade.
* `0021_audit_missing_indexes` adds `ix_inventory_reservations_idempotency_key` and `ix_webhook_created` (declared on models, never migrated).
* Remaining `alembic check` drift is representational only: uniqueness enforced by DB constraints vs. model unique indexes (`orders.order_number`, `orders.fulfilling_capture_id`, `order_returns.return_number`, `shipments.shipment_number`, `retailers.user_id`, `uq_reservation_listing`) and 4 notification indexes named `ix_notifications_*` vs `ix_customer_notifications_*`. No behavioural impact; align models in a later cleanup.
* Local `basket_db` was **not modified**; it is still at `0020`. Apply with `cd backend && .venv/bin/alembic upgrade head`.

### 0.6 How to run the test suite safely

```bash
createdb basket_audit_test   # once
cd backend
DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/basket_audit_test .venv/bin/alembic upgrade head
DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/basket_audit_test .venv/bin/python -m pytest -q
```

### 0.7 Results

| Check | Before audit | After audit |
| :--- | :--- | :--- |
| Backend tests (PostgreSQL 16) | 448 passed | **467 passed, 0 failed, 0 skipped** (19 new audit tests) |
| `ruff check` / `ruff format --check` | clean | clean |
| Endpoints (route walk of the live app) | doc said 145 | **148 operations** (145 under `/api/v1` + `/health`, `/ready`, `/metrics`; 4 are `/catalogue/*` aliases) |

## 1. Executive Summary

This document presents a comprehensive, module-by-module audit of the BASKET backend. The platform is implemented in Python 3.12 using FastAPI and SQLAlchemy 2.0 with asynchronous PostgreSQL drivers (`asyncpg`). The database schema is maintained across 20 linear Alembic migrations (`0001` through `0020_claim_review_history`).

### 1.1 Operational Status Summary

| Status Category | Modules / Capabilities Count | Definition |
| :--- | :---: | :--- |
| **Fully Operational** | 13 Modules (92% of backend scope) | Tested, integrated with database & migrations, verified via 448 unit/integration tests. |
| **Degraded / Resilient** | 2 Components (Kafka & OpenSearch) | Operational with graceful fallbacks (PostgreSQL FTS fallback, offline outbox queuing). |
| **Pending Phase 3** | 9 Features (0% backend code yet) | Defined in product specifications, planned for Phase 3 implementation. |

---

## 2. Core Infrastructure & Reliability Layer

### 2.1 Configuration (`backend/app/core/config.py`)
- **Pydantic Settings Management:** Uses `pydantic-settings` with strict typed environment variable validation.
- **Security Secret Safeguards:** Prevents startup in production if `SECRET_KEY` remains the development default.
- **Dual-Mode Flags:** Provides `has_database`, `has_kafka`, `has_opensearch`, `is_production` helpers for decoupled local, testing, and production execution.
- **Operational Status:** **Working** (Verified via `test_config.py`).

### 2.2 Database Layer (`backend/app/core/database.py`)
- **Engine:** `create_async_engine` configured with connection pooling (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`).
- **Session Management:** `async_sessionmaker(expire_on_commit=False)` provided via dependency injection `get_db()`.
- **Health & Readiness:** `check_db_readiness()` performs `SELECT 1` with a 2-second timeout.
- **Operational Status:** **Working** (Verified via `test_database.py`).

### 2.3 Exception Handling & Logging (`backend/app/core/exceptions.py`, `backend/app/core/logging.py`)
- **Standardized Error Envelope:** All application exceptions inherit from `AppException` and return `{ "error": { "code": "...", "message": "...", "details": ... } }`.
- **HTTP Handlers:** Intercepts `RequestValidationError`, `StarletteHTTPException`, and unhandled root exceptions, logging stack traces with unique `X-Request-ID` correlation identifiers.
- **Operational Status:** **Working** (Verified via `test_exceptions.py`).

### 2.4 Metrics & Observability (`backend/app/core/metrics.py`)
- **Prometheus Instrumentation:** Custom Prometheus registry exposing `/metrics` with bounded cardinality.
- **Tracked Metrics:** `http_requests_total` (counter partitioned by method, normalized path, status code) and `http_request_duration_seconds` (histogram with standard latency buckets).
- **Operational Status:** **Working** (Verified via `test_observability.py`).

---

## 3. Module-by-Module Technical Audit

### 3.1 Identity & Access Management (`backend/app/modules/identity/`)
- **Primary Domain:** User registration, multi-role authentication (`CUSTOMER`, `RETAILER`, `ADMIN`), session tracking, address book.
- **Models:**
  - `User`: UUID primary key, `email` (unique index), `password_hash` (Argon2id), `role`, `status` (`ACTIVE`, `SUSPENDED`).
  - `Session`: UUID primary key, `user_id` (foreign key), `refresh_token_hash`, `expires_at`, `revoked_at`.
  - `Address`: UUID primary key, `user_id`, `recipient_name`, `phone`, `street_address`, `city`, `state`, `postal_code`, `is_default`.
- **Services & Security:**
  - `AuthService`: Password verification via Argon2id, token issuance (15-min JWT access, 7-day refresh cookie).
  - CSRF protection: Double-submit cookie verification.
  - Session revocation: Supports single-session logout and global `logout-all`.
- **Test Coverage:** `tests/test_identity.py` (32 tests passing).
- **Operational Status:** **Working**.

### 3.2 Catalogue & Taxonomy (`backend/app/modules/catalogue/`)
- **Primary Domain:** Multi-category hierarchy, canonical products, product variants, and retailer store listings.
- **Models:**
  - `Category`: Self-referential hierarchy (`parent_id`), `slug` (unique), `is_active`.
  - `Product`: `category_id`, `title`, `brand`, `description`, `is_active`.
  - `ProductVariant`: `product_id`, `sku`, `attributes` (JSONB for size/colour/specs), `mrp`.
  - `RetailerListing`: `retailer_id`, `variant_id`, `selling_price`, `is_active`.
- **Query Optimization:** Strict eager loading via `selectinload` to eliminate $N+1$ query bottlenecks.
- **Public Invariant:** Inactive products or listings belonging to unverified retailers are automatically excluded from public catalogue views.
- **Test Coverage:** `tests/test_catalogue.py` (24 tests passing).
- **Operational Status:** **Working**.

### 3.3 Shopping Cart & Session Merger (`backend/app/modules/cart/`)
- **Primary Domain:** Persistent universal cart supporting guest sessions, authenticated customer carts, and automated guest-to-customer merging.
- **Models:**
  - `Cart`: `user_id` (nullable for guest carts), `session_id` (cookie-tracked), `status` (`ACTIVE`, `MERGED`, `ABANDONED`).
  - `CartItem`: `cart_id`, `listing_id`, `quantity`, unique constraint on `(cart_id, listing_id)`.
- **Merge Engine:**
  - `merge_guest_cart`: Deduplicates identical items by summing quantities up to available listing stock.
  - Automatically transitions guest cart status to `MERGED`.
- **Test Coverage:** `tests/test_cart.py` (28 tests passing).
- **Operational Status:** **Working**.

### 3.4 Pricing & Cryptographic Quotes (`backend/app/modules/pricing/`)
- **Primary Domain:** Dynamic tax computation, promotional discounts, tiered bulk discounts, and cryptographic quote tamper-proofing.
- **Models:**
  - `Quote`: `user_id`, `items_subtotal`, `discount_total`, `tax_total`, `final_total`, `hmac_signature`, `expires_at` (5-minute TTL).
  - `QuoteItem`: `quote_id`, `listing_id`, `unit_price`, `quantity`, `cgst_rate`, `sgst_rate`, `igst_rate`.
  - `Deal`: Platform-wide and retailer-level promotional offers.
- **Security Mechanism:**
  - Quotes are signed using HMAC-SHA256 over `(quote_id, user_id, final_total, expires_at)`.
  - Expired or mutated quotes cannot be used to create orders.
- **Test Coverage:** `tests/test_pricing.py`, `tests/test_quotes.py` (36 tests passing).
- **Operational Status:** **Working**.

### 3.5 Concurrency-Safe Inventory Reservations (`backend/app/modules/inventory/`)
- **Primary Domain:** Multi-location stock tracking, atomic row-level reservation locking, and automatic expiration handling.
- **Models:**
  - `StoreInventory`: `retailer_id`, `listing_id`, `quantity`, `reserved_quantity`, `safety_threshold`.
  - `InventoryReservation`: `reservation_id`, `listing_id`, `quantity`, `expires_at` (10-minute hold), `status` (`ACTIVE`, `COMMITTED`, `RELEASED`).
- **Concurrency Control:**
  - Uses `SELECT ... FOR UPDATE` on `store_inventories` rows to ensure strict serialization of stock holds.
  - Overselling is mathematically prevented under concurrent load.
- **Test Coverage:** `tests/test_reservations.py` (22 tests passing).
- **Operational Status:** **Working**.

### 3.6 Orders, Shipments & Returns (`backend/app/modules/orders/`)
- **Primary Domain:** Immutable order item snapshots, multi-state fulfillment workflow, delivery tracking, post-purchase returns.
- **Models:**
  - `Order`: `order_number`, `user_id`, `total_amount`, `status` (`PENDING`, `CONFIRMED`, `SHIPPED`, `DELIVERED`, `CANCELLED`).
  - `OrderItem`: `order_id`, `listing_id`, `price_snapshot`, `tax_snapshot`, `quantity`, `fulfillment_status`.
  - `Shipment`: `order_id`, `carrier`, `tracking_number`, `status`.
  - `ReturnRequest`: `order_id`, `order_item_id`, `reason`, `status` (`REQUESTED`, `APPROVED`, `REFUNDED`).
- **Transactional Outbox:**
  - `OutboxEvent`: Written in the same atomic transaction as the order.
  - Durable lease coordinator (`outbox_lease`) prevents dual publishing across multi-worker deployments.
- **Test Coverage:** `tests/test_orders.py`, `tests/test_orders_postpurchase.py`, `tests/test_outbox_publisher.py` (64 tests passing).
- **Operational Status:** **Working**.

### 3.7 Payments & Razorpay Gateway (`backend/app/modules/payments/`)
- **Primary Domain:** Razorpay payment orders, webhook ingestion, HMAC signature validation, and refund processing.
- **Models:**
  - `PaymentTransaction`: `order_id`, `razorpay_order_id`, `razorpay_payment_id`, `amount`, `currency`, `status` (`INITIATED`, `SUCCESS`, `FAILED`).
  - `RefundTransaction`: `payment_id`, `razorpay_refund_id`, `amount`, `status`.
- **Security & Integrity:**
  - Verifies `X-Razorpay-Signature` using the webhook secret.
  - Idempotent webhook handling protects against duplicate payment notifications.
  - Dual-mode architecture enables seamless transition between local sandbox and production gateways.
- **Test Coverage:** `tests/test_payments.py` (38 tests passing).
- **Operational Status:** **Working**.

### 3.8 Basket Mission Planner (Phase 2A) (`backend/app/modules/missions/`)
- **Primary Domain:** Goal-oriented shopping planning based on the knapsack algorithm.
- **Core Logic:**
  - Accepts budget targets, household size, and essential categories.
  - Optimizes product selection against price and shipping constraints.
  - Directly syncs selected mission items into the active cart.
- **Test Coverage:** `tests/test_basket_mission.py` (18 tests passing).
- **Operational Status:** **Working**.

### 3.9 Substitute Intelligence (Phase 2B) (`backend/app/modules/substitutes/`)
- **Primary Domain:** Intelligent alternative discovery for out-of-stock, price-hiked, or discontinued items.
- **Engine Rules:**
  - 5 explainable tiers: `CLOSEST_MATCH`, `BUDGET_FRIENDLY`, `BETTER_VALUE`, `PREMIUM_UPGRADE`, `AVAILABLE_NOW`.
  - Computes attribute similarity matrices and unit price differentials.
  - Provides atomic cart replacement endpoint (`/api/v1/cart/items/{id}/replace`).
- **Test Coverage:** `tests/test_substitute_intelligence.py` (26 tests passing).
- **Operational Status:** **Working**.

### 3.10 Basket Intent Memory (Phase 2C) (`backend/app/modules/intent/`)
- **Primary Domain:** Customer preference retention, dietary rules, brand preferences, recurring shopping intentions.
- **Models:**
  - `UserIntentProfile`: `user_id`, `personalization_enabled` (Strict default: `False`), `dietary_tags`, `preferred_brands`, `excluded_brands`.
  - `RecurringIntention`: `profile_id`, `title`, `frequency_days`, `target_category_id`, `is_active`.
- **Privacy & Consent:**
  - Opt-in enforcement: personalization must be explicitly turned on by the user.
  - Full data erasure endpoint (`DELETE /api/v1/intent/clear-all`) purges preferences and recurring items.
- **Test Coverage:** `tests/test_intent_memory.py` (22 tests passing).
- **Operational Status:** **Working**.

### 3.11 Product Passport & Claim Moderation (Phase 2D) (`backend/app/modules/passport/`)
- **Primary Domain:** Canonical product specifications, retailer listing claims, and immutable admin review moderation queue.
- **Models:**
  - `ProductPassport`: `product_id`, `origin_country`, `certifications`, `ingredients`, `technical_specs`.
  - `ListingPassport`: `listing_id`, `batch_number`, `manufacturing_date`, `expiry_date`, `warranty_months`.
  - `PassportClaim`: `listing_passport_id`, `claim_type`, `claim_value`, `evidence_url`, `status` (`PENDING`, `VERIFIED`, `REJECTED`).
  - `PassportClaimReviewHistory`: `claim_id`, `status`, `rejection_reason`, `reviewed_by_user_id`, `reviewed_at`, `claim_snapshot`, `version`.
- **Audit Lineage:**
  - Revisions to previously reviewed claims automatically transition back to `PENDING` without erasing historical moderation records.
  - Rejection reasons and reviewer IDs are preserved in append-only history.
- **Test Coverage:** `tests/test_product_passport.py` (24 tests passing).
- **Operational Status:** **Working**.

### 3.12 Retailer & Admin Management Portals (`backend/app/modules/retailer/`, `backend/app/modules/admin/`)
- **Primary Domain:** Retailer onboarding, document verification, store profile management, inventory adjustments, and platform-wide moderation.
- **Models:**
  - `RetailerProfile`: `user_id`, `business_name`, `gstin`, `pan`, `is_verified`.
  - `RetailerDocument`: `retailer_id`, `document_type`, `document_url`, `verification_status`.
- **Portal Security:** Strict role-based gatekeeping preventing IDOR access across competing retailers.
- **Test Coverage:** `tests/test_multi_role_portals.py`, `tests/test_admin_marketplace_moderation.py` (40 tests passing).
- **Operational Status:** **Working**.

### 3.13 Universal Search & Discovery (`backend/app/modules/search/`, `backend/app/core/search/`)
- **Primary Domain:** Faceted discovery across title, category, brand, price ranges, and inventory status.
- **Engine Infrastructure:**
  - OpenSearch 2.x cluster index: `basket_products_v1`.
  - Background index synchronizer via Kafka events.
  - Automated circuit breaker with transparent fallback to PostgreSQL full-text search (`to_tsvector`).
- **Test Coverage:** `tests/test_search.py`, `tests/test_opensearch.py` (24 tests passing).
- **Operational Status:** **Working / Resilient**.

---

## 4. Database Schema & Integrity Constraints Table

| Table Name | Primary Key | Foreign Keys | Key Constraints & Indexes |
| :--- | :--- | :--- | :--- |
| `users` | `id` (UUID) | None | Unique index on `email` |
| `sessions` | `id` (UUID) | `user_id -> users.id` | Index on `refresh_token_hash`, `expires_at` |
| `addresses` | `id` (UUID) | `user_id -> users.id` | Index on `(user_id, is_default)` |
| `categories` | `id` (UUID) | `parent_id -> categories.id`| Unique index on `slug` |
| `products` | `id` (UUID) | `category_id -> categories.id`| Index on `(category_id, is_active)` |
| `product_variants` | `id` (UUID) | `product_id -> products.id`| Unique index on `sku` |
| `retailer_profiles`| `id` (UUID) | `user_id -> users.id` | Unique index on `gstin`, `user_id` |
| `retailer_listings`| `id` (UUID) | `retailer_id`, `variant_id` | Unique index on `(retailer_id, variant_id)` |
| `store_inventories`| `id` (UUID) | `retailer_id`, `listing_id` | Unique index on `(retailer_id, listing_id)`, check `quantity >= 0` |
| `inventory_reservations`| `id` (UUID) | `listing_id -> retailer_listings.id` | Index on `(status, expires_at)` |
| `carts` | `id` (UUID) | `user_id -> users.id` | Index on `(user_id, status)`, `session_id` |
| `cart_items` | `id` (UUID) | `cart_id`, `listing_id` | Unique index on `(cart_id, listing_id)` |
| `quotes` | `id` (UUID) | `user_id -> users.id` | Index on `expires_at` |
| `orders` | `id` (UUID) | `user_id -> users.id` | Unique index on `order_number`, index on `status` |
| `order_items` | `id` (UUID) | `order_id`, `listing_id` | Foreign keys with cascade constraints |
| `outbox_events` | `id` (UUID) | None | Index on `(status, leased_until)` |
| `consumer_inbox` | `message_id` (VARCHAR)| None | Unique primary key for idempotency |
| `product_passports`| `id` (UUID) | `product_id -> products.id`| Unique index on `product_id` |
| `listing_passports`| `id` (UUID) | `listing_id -> retailer_listings.id`| Unique index on `listing_id` |
| `passport_claims` | `id` (UUID) | `listing_passport_id` | Index on `status` |
| `passport_claim_review_histories` | `id` (UUID) | `claim_id -> passport_claims.id`| Index on `(claim_id, version)` |
| `user_intent_profiles` | `id` (UUID) | `user_id -> users.id` | Unique index on `user_id` |
| `recurring_intentions` | `id` (UUID) | `profile_id -> user_intent_profiles.id` | Index on `(profile_id, is_active)` |

---

## 5. Backend Test Suite Verification Summary

The test suite runs with pytest against an isolated SQLite memory database with simulated PostgreSQL constructs, avoiding any risk to production data.

```
============================== 448 passed in 18.42s ==============================
```
- Total test files: 28
- Total passed tests: 448
- Total failed tests: 0
- Code coverage: > 91% across all business modules.
