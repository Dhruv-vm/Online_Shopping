# BASKET — Task Breakdown and Ownership

> Fill in the two developer names/handles and ownership before parallel coding. This is a suggested split; adjust it to actual strengths, but keep shared foundation work coordinated.

## 1. Assign roles

| Responsibility | Owner |
|---|---|
| Integration owner | **Fill in** |
| Frontend foundation | **Fill in** |
| Backend foundation | **Fill in** |
| Database/Alembic migration owner | **Fill in one person** |
| Aiven account/service setup | **Fill in** |
| Demo/release owner | **Fill in** |

## 2. Phase 0 — jointly agree (do not parallelize prematurely)

- [x] Create repository and `integration` branch.
- [x] Add these project documents.
- [x] Confirm stack and environment variable names.
- [x] Agree API envelope, IDs, money representation, timestamps, pagination.
- [x] Agree initial logical data model.
- [x] Assign module/file ownership.
- [x] Create `.env.example` with placeholders only.
- [x] Establish lint, format, type-check, and test commands.

## 3. Phase 1 — Catalogue & Storefront Foundation

- [x] Next.js app shell, responsive navigation header with search and mobile drawer.
- [x] Centralized, strongly-typed API client with catalogue endpoints and error envelope.
- [x] FastAPI modular monolith catalogue models (Retailers, Categories, Products, Variants, Images, Listings, Inventory).
- [x] Alembic migration `0002_catalogue_schema` with clean upgrade and downgrade.
- [x] Catalogue endpoints (`GET /api/v1/categories`, `GET /api/v1/retailers`, `GET /api/v1/products`, `GET /api/v1/products/{id}`).
- [x] Idempotent, repeatable seed dataset covering 7 Indian retail categories and multiple retail partners.
- [x] Catalogue storefront UI (Homepage showcase, Department directory, Products browsing with filters/sorting/pagination, Product detail with variant/retailer picker).
- [x] Full quality gates passing (24/24 pytest backend tests, 10/10 frontend tests, Ruff lint/format, TypeScript type-check, Next.js build).

## 4. Phase 2 — Mandatory Commerce Engine

- [x] **Phase 2A — Identity, Authentication & Address Management (Backend & Frontend):**
  - [x] Backend Models: `User`, `UserSession`, `Address` with partial unique index for single default address.
  - [x] Backend Security: Argon2id password hashing, JWT access tokens, refresh token rotation with pessimistic row locking (`for_update=True`) and family reuse detection.
  - [x] Session Revocation: Instantaneous access token revocation via JWT `sid` claim checked against database session revocation status.
  - [x] Backend Protection: Sliding-window login rate limiting, double-submit CSRF protection with Origin header validation, email normalization.
  - [x] Migration: Alembic `0003_identity_schema` with clean upgrade and downgrade.
  - [x] Backend APIs: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/logout-all`, `GET /api/v1/users/me`.
  - [x] Address Management APIs: `GET /api/v1/addresses`, `POST /api/v1/addresses`, `PATCH /api/v1/addresses/{id}`, `DELETE /api/v1/addresses/{id}` with 6-digit Indian PIN code validation, auto-default for first address, and fallback promotion on default deletion.
  - [x] Frontend Auth Engine: `AuthProvider` context, secure HTTP-only cookie session handling, single-flight token refresh preventing duplicate refresh requests, automatic CSRF token injection from double-submit cookie.
  - [x] Frontend Pages: Customer registration (`/register`), login (`/login`), account overview (`/account`), address book (`/account/addresses`).
  - [x] Frontend Experience: Route protection (`<ProtectedRoute>`), session expiry handling, responsive address book with empty state, default badge, edit modal, delete confirmation, Indian state selector, 6-digit PIN code validation.
  - [x] Header Integration: Dynamic customer session status, user greeting, quick links, and logout action.
  - [x] Quality Gates: 51/51 backend pytest tests passing, 25/25 frontend tests passing, 0 Ruff errors, 0 ESLint errors, TypeScript typecheck passing, Next.js production build passing.
- [x] **Phase 2B — Persistent Cart Domain & Guest Migration (Backend & Frontend):**
  - [x] Backend Models: `Cart` and `CartItem` in PostgreSQL with `chk_cart_ownership`, `chk_cart_status`, `chk_cart_item_quantity`, partial unique index `uq_cart_customer_active`, and unique index `uq_cart_listing`.
  - [x] Guest Token Lifecycle: 256-bit cryptographically secure token (`secrets.token_urlsafe(32)`), stored only as SHA-256 hash in DB, delivered via HTTP-only cookie `basket_guest_cart` (30-day expiry).
  - [x] Dynamic Pricing & Live Inventory: Unit prices and subtotals derived dynamically from catalogue listings; live available stock calculated as `max(0, on_hand - reserved)`. Cart validates availability read-only without reserving stock (inventory reservations belong to Phase 2D).
  - [x] Migration: Alembic `0004_cart_schema` with clean upgrade, downgrade, and re-upgrade verification.
  - [x] Cart APIs: `GET /api/v1/cart`, `POST /api/v1/cart/items`, `PATCH /api/v1/cart/items/{id}`, `DELETE /api/v1/cart/items/{id}`, `DELETE /api/v1/cart`, `POST /api/v1/cart/merge`.
  - [x] Atomicity & Concurrency: Pessimistic row locking (`with_for_update()`) on Cart mutations; transactional guest-to-customer cart migration with conflict resolution policy (capping combined quantity to 10 or available stock).
  - [x] Frontend Cart Engine: `CartProvider` context, automatic guest cart cookie sync, background auto-merge on customer login/register, live totals, quantity updates, item removal, cart clearance.
  - [x] Frontend Cart Page: `/cart` with multi-retailer grouping, item thumbnail and attributes, stock warnings, quantity stepper, clear cart confirmation, and order summary breakdown.
  - [x] Header & Catalogue Integration: Real-time cart quantity badge in desktop and mobile header navigation, quantity selector and "Add to Basket" controls on product detail page.
  - [x] Quality Gates: 60/60 backend pytest tests passing, 33/33 frontend tests passing, 0 Ruff errors, TypeScript typecheck passing, Next.js production build passing.
- [x] **Phase 2C — Pricing, Taxes & Persistent Quotes (Backend & Frontend):**
  - [x] Listing-level HSN tax brackets (0%, 5%, 12%, 18%, 28%) and CGST/SGST vs IGST engine with deterministic integer paise rounding reconciliation (`cgst + sgst + igst == total_tax`, `taxable_base + total_tax == selling_price`).
  - [x] Extensible discount engine (`discounts` table with listing-level fixed amount or percentage basis points, validity window, and non-negative price floor).
  - [x] Delivery threshold logic (₹0 for $\ge$ ₹499; ₹49 for $<$ ₹499 per retailer) with multi-retailer aggregation.
  - [x] Immutable `checkout_quotes` and `checkout_quote_items` models with 15-minute TTL, ownership check constraints, and single-use consumption guarantee.
  - [x] Quote validation & repricing: detects expired quotes, price changes, GST updates, and stock deficits; supersedes stale quotes without deleting historical audit trail.
  - [x] Alembic migration `0005_pricing_quotes_schema` adding `hsn_code` and `gst_rate_basis_points` to `product_listings`, `state` to `retailers`, and creating `discounts`, `checkout_quotes`, `checkout_quote_items`.
  - [x] Quote APIs: `POST /api/v1/quotes`, `GET /api/v1/quotes/{id}`, `POST /api/v1/quotes/{id}/validate`, `POST /api/v1/quotes/{id}/refresh`, `GET /api/v1/quotes`, `POST /api/v1/checkout/quote`.
  - [x] Frontend Quote Client & Types: `createQuote`, `getQuote`, `validateQuote`, `refreshQuote`, `listQuotes` in `@/lib/api/quotes` and `@/types`.
  - [x] Frontend Cart UI: Live guaranteed quote display on `/cart`, 15-minute countdown timer, repricing notice banner with "Accept & Refresh Quote" CTA, line-item HSN and GST rate badges, per-retailer delivery breakdown with free delivery progress, and statutory Indian GST reconciliation breakdown.
  - [x] Quality Gates: 81/81 backend pytest tests passing, 40/40 frontend tests passing, 0 Ruff errors, TypeScript typecheck passing, Next.js production build passing.
- [x] **Phase 2D — Inventory Reservations & Concurrency Protection (Backend & Frontend):**
  - [x] Lock ordering by `listing_id` in deterministic ascending order to mathematically eliminate PostgreSQL deadlocks across multi-item checkouts.
  - [x] Atomic all-or-nothing multi-retailer inventory reservations (`inventory_reservations` and `inventory_reservation_items`).
  - [x] Configurable reservation TTL (`settings.RESERVATION_TTL_MINUTES`, default 10 minutes) and automated expiry cleanup worker (`POST /api/v1/internal/reservations/cleanup-expired`).
  - [x] Idempotent reservation creation with `Idempotency-Key` header and partial unique indexes.
  - [x] Reversible Alembic migration `0006_inventory_reservations` maintaining single migration head.
  - [x] Explicit state machine: `ACTIVE` -> `CONFIRMED` / `RELEASED` / `EXPIRED` with strict transition checks.
  - [x] High-concurrency anti-oversell tests against live PostgreSQL: 5 concurrent requests for 1 available unit verified to yield exactly 1 success and 4 structured 409 errors with 0 oversell.
  - [x] Frontend reservation client and cart integration: stock hold countdown timer, manual release action, shortage error alerts, and seamless recovery.
  - [x] Quality Gates: 102/102 backend pytest tests passing, 47/47 frontend tests passing, 0 Ruff errors, TypeScript typecheck passing, Next.js production build passing.
- [x] **Phase 2E — Orders, Outbox & Checkout Orchestration:**
  - [x] Immutable order item snapshots and scoped idempotency (`idempotency_records`).
  - [x] Decoupled checkout transaction boundaries with unpaid order lifecycle (`PENDING_PAYMENT`, `NOT_INITIATED`) and reservation allocation (`ALLOCATED_TO_ORDER`).
  - [x] Circular foreign key flush sequencing between `orders` and `inventory_reservations`.
  - [x] Selective cart reconciliation preserving unquoted cart items.
  - [x] Transactional outbox table (`outbox_events`) with zero-PII event payloads (`order.created`).
  - [x] Scoped order retrieval (`GET /api/v1/orders`, `GET /api/v1/orders/{id}`) with strict anti-IDOR isolation for customers and guests.
  - [x] Alembic migration `0007_orders_outbox_schema` with clean upgrade and downgrade.
  - [x] Frontend order client (`@/lib/api/orders`), types (`@/types`), and test suite (`lib/api/orders.test.ts`).
  - [x] Quality Gates: 136/136 backend pytest tests passing, 53/53 frontend tests passing, 0 Ruff errors, TypeScript typecheck passing, Next.js production build passing.
- [x] **Phase 2F — Razorpay Payments, Capture Ledger, Webhooks, Multi-Refund & Reconciliation (Architecture v3.1.4 Master Specification):**
  - [x] **Slice A: Configuration & Async HTTPX Razorpay Client:**
    - Settings with `SecretStr` for `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `INTERNAL_SERVICE_SECRET`.
    - Native `RazorpayClient` (`modules/payments/client.py`) with Basic Auth, timeouts (5s connect, 10s read), constant-time HMAC-SHA256 signature verification over raw ASGI bytes.
    - Verified Razorpay REST API endpoints including `GET /v1/orders?receipt={receipt}` and `POST /v1/payments/{id}/refund` with `X-Refund-Idempotency`.
  - [x] **Slice B: Database Schema & Migration `0008` (Capture Ledger Architecture & Single Source of Truth):**
    - Tables: `payments`, `payment_captures`, `payment_refunds`, `webhook_events`.
    - Retention & Constraints: `customer_id UUID REFERENCES users(id) ON DELETE RESTRICT` across all financial tables; `uq_payments_id_order UNIQUE (id, order_id)`.
    - Capture Ledger: `payment_captures` recording every distinct provider capture (`uq_payment_captures_provider_payment` on `provider_payment_id`).
    - Capture Ledger & Eligibility Immutability: PostgreSQL trigger `trg_payment_captures_protect_immutable` disallowing DELETE and disallowing UPDATE of core captured facts and eligibility (`provider`, `provider_payment_id`, `order_id`, `payment_id`, `amount_paise`, `currency`, `captured_at`, `is_fulfillment_eligible`).
    - Fulfillment Single Source of Truth: `orders.fulfilling_capture_id UUID UNIQUE` with composite foreign key `CONSTRAINT fk_orders_fulfilling_capture_same_order FOREIGN KEY (fulfilling_capture_id, id) REFERENCES payment_captures(id, order_id) ON DELETE RESTRICT`.
    - Dual INSERT/UPDATE Fulfillment Trigger: PostgreSQL trigger `trg_orders_fulfilling_capture_immutable` running `BEFORE INSERT OR UPDATE ON orders`, preventing inserting with ineligible/foreign captures, overwriting, clearing, or assigning non-eligible captures.
    - Composite foreign keys for refunds: `fk_refunds_capture_same_order` and `fk_refunds_payment_same_order`.
    - `webhook_events` claim & lease columns: `claimed_by`, `claim_expires_at`.
    - Reversible Alembic downgrade script.
  - [x] **Slice C: Payment Initiation Service & API:**
    - Pre-gateway two-transaction pattern: Transaction 1 inserts `CREATING` row, attempt number, and locks order; Transaction 2 associates `provider_order_id` and sets `PENDING`.
    - Ambiguous creation protection: network timeouts / lost responses mark `CREATION_AMBIGUOUS` and block all retries until provider reconciliation. Empty search results NEVER trigger automatic failure; operational review SLA of 60m holds quarantined stock in `ALLOCATED_TO_ORDER`.
    - Enforce unique constraints `uq_payments_order_idempotency` and `uq_payments_order_attempt`.
    - Deterministic receipt format: `{order_number}-{attempt_number}`.
    - Expose `POST /api/v1/orders/{order_id}/payments` with customer/guest authorization.
  - [x] **Slice D: Signature Verification, Server-Side Capture & Order Confirmation:**
    - Validate signature, amount, currency against order record.
    - Automated server-side capture workflow for `status == 'authorized'`.
    - Enforce single fulfillment: insert/update `payment_captures` (`is_fulfillment_eligible = TRUE`), set `orders.fulfilling_capture_id = capture.id`, `orders.status = CONFIRMED`, and `inventory_reservations.status = CONFIRMED` in one transaction.
    - Partial capture rejection: record `payment_captures` (`reconciliation_status = 'PARTIAL_CAPTURE_REJECTED'`), cancel order, dispatch automated full refund, refuse stock confirmation.
    - Expose `POST /api/v1/orders/{order_id}/payments/verify`.
  - [x] **Slice E: Three-Phase Claim-and-Process Webhook Ingestion & Processing:**
    - Phase 1 (Ingestion): raw ASGI body HMAC verification, payload sanitization (scrub card/CVV), deduplication on `x-razorpay-event-id`, durable insert to `webhook_events` (`status = PENDING`), return HTTP 200. Return HTTP 200 on duplicate (`ALREADY_INGESTED`).
    - Phase 2A (Claiming): lease claiming via short transaction with `claim_expires_at = NOW() + 30s` and `SKIP LOCKED`, releasing webhook row lock before business logic.
    - Phase 2B (Business Execution): downward lock hierarchy (`orders` $\rightarrow$ `payments` $\rightarrow$ `payment_captures` $\rightarrow$ `payment_refunds` $\rightarrow$ `res` $\rightarrow$ `inv`), idempotent state transitions.
    - Phase 2C (Acknowledgment): separate short transaction marking `status = 'PROCESSED'`.
    - Duplicate capture handling: record in `payment_captures` as `OVERPAYMENT_ANOMALY`, dispatch automated full refund, never confirm stock twice or alter `orders.fulfilling_capture_id`.
    - Worker crash recovery: post-commit crash proven idempotent; expired leases reclaimed safely.
    - Expose `POST /api/v1/payments/webhook`.
  - [x] **Slice F: Multi-Refund Engine & Late-Capture Protection:**
    - `PaymentService.create_refund` with row-level capture lock and atomic balance validation `sum(active) + amount <= capture.amount_paise`.
    - Official header `X-Refund-Idempotency: {refund.id}` and body `receipt`.
    - Late capture automated full refund when reservation is `RELEASED`.
    - Expose `POST /api/v1/orders/{order_id}/refunds`.
  - [x] **Slice G: Background Reconciliation Service & Internal API:**
    - Missed-webhook payment recovery querying `GET /v1/orders/{order_id}/payments` to reconcile captures, update ledger, and confirm order fulfillment when callbacks/webhooks are lost.
    - PostgreSQL savepoint isolation (`begin_nested()`) wrapping `confirm_reservation()` so statement failures isolate cleanly to `REQUIRES_RECONCILIATION` without poisoning the outer payment ledger transaction.
    - Fail-closed production configuration rejecting missing, placeholder, or mock Razorpay credentials without leaking secrets.
    - Reconciler for ambiguous `CREATION_AMBIGUOUS` attempts via `GET /v1/orders?receipt={receipt}`, pending payments older than `pending_cutoff_minutes`, and expired webhook leases.
    - Administrative endpoint `POST /api/v1/internal/payments/{id}/resolve-ambiguity` with audit logging for manual review action (`CONFIRM_ABSENT` vs `LINK_PROVIDER_ORDER`).
    - Automated 75-minute fail-safe quarantine escalation job: cancels order (`AMBIGUITY_SLA_EXPIRED`), fails attempts (`OPERATIONAL_SLA_EXPIRED`), releases reservations exactly once, and leaves order permanently cancelled.
    - Expose `POST /api/v1/internal/payments/reconcile-pending` protected by `X-Internal-Service-Key` with configurable `pending_cutoff_minutes`.
  - [x] **Slice H: Frontend Integration & Test Suite:**
    - Dynamic script loader for `checkout.js`, modal configuration, customer/guest checkout flows, polling fallback.
    - Comprehensive pytest suite (176 tests in `backend/tests/`) covering:
      - Test A: Missed webhook payment recovery fulfills order, confirms reservation, and emits outbox event.
      - Test B: Repeated reconciliation runs are idempotent.
      - Test C: Late webhook arriving after reconciliation preserves fulfillment without duplicate stock deduction.
      - Test D: Invalid gateway payments (partial capture, late capture, overpayment, failed) rejected/refunded without stock confirmation.
      - Test E: Concurrent webhook and reconciliation worker race cleanly serialized via row locks.
      - Test F: Savepoint isolates inventory confirmation statement failure and safely recovers.
      - Test G: Production rejects missing, placeholder, or mock Razorpay credentials.
      - Scenario A: One exact successful capture (one ledger record, one fulfillment, one inventory deduction).
      - Scenario B: Duplicate webhook for same capture (one ledger record, no duplicate side effects).
      - Scenario C: Two distinct provider captures for same order (both persist in ledger, first fulfills, second auto-refunded as overpayment anomaly).
      - Scenario D: Database failure after capture (reconciler recovers capture into ledger).
      - Scenario E: Unexpected second capture after order confirmed (recorded and refunded without touching inventory).
      - Scenario F: Partial capture (recorded in ledger, order cancelled, auto-refunded, stock released).
      - Scenario G: Multiple partial refunds against capture (sum of refunds strictly bounded by capture amount).
      - Scenario H: Capture fact and eligibility immutability trigger blocks SQL UPDATE or DELETE on core financial facts or `is_fulfillment_eligible`.
      - Scenario I: Order fulfillment single source of truth trigger blocks re-assignment, clearing, or non-eligible capture linkage on UPDATE.
      - Scenario J: Order INSERT with ineligible capture (`is_fulfillment_eligible = FALSE`) is rejected by database trigger.
      - Scenario K: Order INSERT with another order's capture is rejected by composite foreign key / trigger.
      - Scenario L: Updating a selected capture's eligibility from TRUE to FALSE is rejected by capture immutability trigger.
      - Scenario M: Refund and reconciliation updates on `payment_captures` / `payment_refunds` do not erase or invalidate historical fulfillment relationship in `orders`.
      - Scenario N: Concurrent capture processors (modal callback vs webhook) serialize via order row lock and produce at most one fulfilling capture.
      - Scenario O: Terminal 75-minute SLA job releases stock, and subsequent late capture triggers 100% auto-refund without order re-activation.
      - Ambiguous order creation timeout and 60m quarantine hold.
      - Customer account anonymization & session revocation test.
      - Webhook worker crash after business commit but before completion (idempotent recovery).
      - Older authorized event arriving after capture.
      - `payment.failed` followed by `payment.captured`.
      - Refund request timeout and retry without duplicate refund.
- [ ] **Phase 2G — Storefront UI & End-to-End Verification:**
  - [ ] Cart drawer, full cart page, multi-step checkout stepper, order tracking view.

## 5. Phase 3 — Kafka Event Streaming, Outbox Publisher, OpenSearch & Universal Search

Authoritative Specification: `PHASE_3_ARCHITECTURE.md` (Version 2.0.0 Distributed Systems & Reliability Correction)

- [x] **Phase 3A — Infrastructure, Configuration & Event Contracts:**
  - [x] Add `aiokafka>=0.11.0` optional dependency and configuration settings for Aiven Kafka (`KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL`, TLS certificates, SASL credentials).
  - [x] Implement Pre-Deployment Validation Checklist verifying provisioned Aiven tier, partition limits, and single/multi-broker replication constraints.
  - [x] Implement `EventEnvelope` model with strict versioning, `aggregate_version`, partition keys, ISO-8601 timestamps, and zero-PII payload validation (customer identifiers excluded).
  - [x] Define Kafka topic topology (`basket.events.orders`, `basket.events.payments`, `basket.events.catalogue`, `basket.events.inventory`, `basket.events.dead-letter`).
  - [x] Provide `MockKafkaProducer` for local development and CI testing without live Aiven credentials.
  - [x] Acceptance Criteria: Envelope validation tests pass; Level 1/Level 2 PII detection fails closed; local environment runs cleanly without credentials.

- [x] **Phase 3B — Transactional Outbox Publisher:**
  - [x] Alembic migration `0009_outbox_lease` adding `version` to `orders`, and `aggregate_version`, `claimed_by`, `claim_expires_at`, `next_attempt_at`, `correlation_id` and `PROCESSING` status to `outbox_events`.
  - [x] Implement authoritative aggregate root versioning derived transactionally from `Order.version` under exclusive row locks, guaranteeing strictly monotonic event sequences ($V_1 < V_2 < \dots < V_n$).
  - [x] Implement multi-worker lease claiming with `SELECT ... FOR UPDATE SKIP LOCKED`, 30-second leases, and bounded batch sizes (<=20 items).
  - [x] Enforce lease ownership on update (`WHERE id = :event_id AND claimed_by = :worker_id`).
  - [x] Outbox publisher worker executing bounded exponential backoff with full jitter ($T_{backoff} = \min(300, 2^{retry\_count} + \text{jitter})$) and authoritative `MAX_RETRIES = 5` threshold.
  - [x] Aggregate version preservation across retries, crash recovery, and OpenSearch `external_gte` deduplication simulation.
  - [x] Distinction between transient network errors and permanent serialization failures (`FAILED` status).
  - [x] Application lifecycle management, 15-second batch window deadline, and production mock rejection.
  - [x] Acceptance Criteria: Multi-worker concurrency tests prove zero duplicate processing races; publisher crash after Kafka ACK safely recovers; no skipped outbox rows.

- [x] **Phase 3C — Kafka Consumers & Reliability Engine:**
  - [x] Alembic migration `0010_consumer_inbox` creating `consumer_inbox` table with unique constraint on `(consumer_group, event_id)` and `order_summary_projections`.
  - [x] Strategy A (PostgreSQL-only consumers): Atomic DB transaction enclosing inbox insert and business mutation, followed by manual offset commit.
  - [x] Strategy B architecture defined (OpenSearch consumers with `version_type="external_gte"`, scheduled for Phase 3D).
  - [x] Generic `BaseKafkaConsumer` managing consumer groups, cooperative sticky rebalancing, partition pause/resume on retry, and dead-letter queue routing (`basket.events.dead-letter`).
  - [x] Acceptance Criteria: Injected duplicate event deliveries produce effectively-once business side effects; consumer crash before commit replays safely; offset committed only after DLQ ACK confirmed. All 296 tests passing.

- [x] **Phase 3D — OpenSearch Indexing & Derived Read Model:**
  - [x] OpenSearch async client architecture implemented (`OpenSearchClient` and `MockOpenSearchClient`) with SSL verification, pooling, and external_gte versioning.
  - [x] Product-Centric `basket_products_v1` index mapping with custom analyzers, embedded retailer listings, and keyword fields.
  - [x] Zero-downtime blue/green index alias management (`IndexManager`) supporting atomic alias swaps and rollbacks.
  - [x] Incremental indexing consumer (`OpenSearchConsumer`) implementing Strategy B with optimistic concurrency (`external_gte`) and safe 409 conflict discarding.
  - [x] Database reconciliation function (`IndexManager.reconcile_from_database`) rebuilding index from PostgreSQL.
  - [x] Acceptance Criteria: Multi-retailer variant document correctly indexes price ranges and inventory; replaying older product events rejects stale regression (409 Conflict); index management lifecycle and DB reconciliation verified. All tests passing.

- [x] **Phase 3E — Universal Multi-Category Search API & Storefront Fallback:**
  - [x] Expose `GET /api/v1/search` with keyword query, multi-category facets, brand/retailer filters, price range, stock flags, sorting, and pagination.
  - [x] Expose `GET /api/v1/search/suggestions` for instant prefix autocomplete.
  - [x] Three-state circuit breaker (`SearchCircuitBreaker`) with 5-failure trip threshold and 30s recovery window.
  - [x] Transparent fallback to PostgreSQL SQL search with reduced faceting under fallback load.
  - [x] Frontend search integration with dedicated search page (`frontend/app/search/page.tsx`), header search linking, and API client methods (`searchProducts`, `getSearchSuggestions`).
  - [x] Acceptance Criteria: Universal search works across groceries, fashion, electronics, and home; search remains fully functional via SQL fallback when OpenSearch is unavailable; circuit breaker protects database from connection exhaustion. Frontend production build passes.

- [x] **Phase 3F — Observability, Metrics & Operational Dashboards:**
  - [x] In-memory Prometheus metrics registry (`app.core.metrics.REGISTRY`) exposing counters, histograms, and gauges at `GET /metrics`.
  - [x] Request metrics middleware tracking HTTP latency and request counts with bounded label cardinality (no PII or customer IDs).
  - [x] Health and readiness probes (`/ready`) reporting detailed component checks for database, kafka, and opensearch.
  - [x] Prometheus alerting rules (`deploy/observability/alerts.yml`) and Grafana dashboard (`deploy/observability/dashboards/basket-platform.json`).
  - [x] Acceptance Criteria: Full observability metrics verified; health checks report `ready` (or `degraded` in dev) cleanly. All 338 backend tests passing.

## 6. Phase 4 — Sale Storm proof

- [ ] Create controlled test inventory.
- [ ] Run concurrent checkout attempts.
- [ ] Verify no oversell.
- [ ] Verify all-or-nothing multi-item reservation.
- [ ] Verify expiry releases stock once.
- [ ] Capture test output for demo.

## 7. Phase 5 — choose differentiators

Choose **one or two** based on remaining time and quality:

| Feature | Small credible slice |
|---|---|
| Quinn | Generate expiring quote; backend enforces discount floor |
| Apni Bhasha | Search across one or two tested languages |
| Basket Suggests | Compare same exact variant across two sellers |
| Demand Gap Radar | Aggregate zero-result searches by region/category |
| Basket Mission | Generate one editable cross-category shopping plan |
| Demand Exchange | One Demand Box and one retailer offer response |
| Product Proof | Show provenance and evidence for selected claims |
| BASKET LIVE | Voice input/output behind a provider adapter, only if verified |

## 8. Phase 6 — freeze and demo

- [ ] Stop adding features.
- [ ] Run clean setup and migration.
- [ ] Run automated tests and end-to-end smoke test.
- [ ] Verify PostgreSQL, Kafka, OpenSearch live behaviour.
- [ ] Test failure states and empty catalogue.
- [ ] Remove debug routes and secrets.
- [ ] Seed a predictable demo dataset.
- [ ] Rehearse the demo with a backup recording/screenshots.
- [ ] Merge only tested commits to `main`.
