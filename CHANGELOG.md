# BASKET — Changelog

All notable changes to the BASKET project are documented in this file.  
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0-mc] — 2026-11-21 — Marketplace completion (local branch `feature/marketplace-completion`)

Base `integration` @ `2610a1e`. Not pushed, merged or deployed. Detailed report: [`docs/MARKETPLACE_COMPLETION.md`](docs/MARKETPLACE_COMPLETION.md).

### Added
- Storefront homepage (18 sections driven by live data), BASKET brand palette, role-aware header/footer, policy pages.
- Twelve-language interface (en, hi, kn, ta, te, ml, bn, mr, gu, pa, or, ur; Urdu right-to-left) with cookie, localStorage and account persistence; locale-aware money, numbers and dates. 290 core keys translated per language; the rest falls back to English. Coverage is partial: ≈32 % of visible page strings are translated (shell, sign-in, homepage and new portal pages); core shopping and retailer operations pages remain English.
- Common login with backend-role redirects and expired-session handling; retailer onboarding (GSTIN, documents, resubmission) with a restricted portal until approval.
- Retailer: real dashboard KPIs, analytics definitions (gross sales, settled revenue, paid/fulfilled orders, units dispatched, pending payment), listing photos, group-buy templates, price insights.
- Admin: user management (suspend/reinstate with session revocation), orders, audit log of admin mutations, system health, RFQ moderation, group-buying, auctions, price-data quality, verification desk, canonical product images.
- Phase 3: customer-started group buys (3B); rule-based deal assistant (3D); price comparison, alerts, retailer insights and demo-labelled history (3F); OCR confidence and labelled manual fallback (3I).
- Reversible data quarantine for test fixtures; demonstration marketplace seed and `*_demo`-only reset script.
- Migrations `0031`–`0034`; `scripts/verify-migrations.sh`; `scripts/audit-features.sh`; E2E API journeys A–F.

### Fixed
- Offers saved as 0 % (percentages now stored in basis points).
- Unpaid orders could be packed/shipped; analytics counted unpaid orders.
- Tests wrote to the development database (now always a `*_test` database).
- Retailer and admin sessions could add to cart, quote, reserve, order and start payment through the API (`403 BUSINESS_ACCOUNT_CANNOT_SHOP`).
- Store links pointed at a non-existent `/retailers/<slug>` page.
- A stale saved language overrode the server-rendered one.
- Checkout: blank when opened directly, developer copy shown to shoppers, raw address-ID field, refresh lost the payment step.
- Eight foreign-key columns without an index (`0034`).
- Intermittent `test_budget_shortfall_handling` and `test_mission_recommendation_personalized_by_intent` failures caused by shared test-database state.
- List to Basket offered search matches the database could not sell.
- Admin suspension and RFQ-moderation reasons were discarded; now stored in the audit log.
- Retailer RFQ bid could be submitted empty.

### Known limitations
See `DISCREPANCY_REGISTER.md` §MC (open items MC-01…MC-09).

---

## [1.1.0-phase3] — 2026-11-20 — Phase 3 marketplace (local branch `feature/phase-3-advanced-marketplace`)

### Added
- 3A Demand Gap (signals, pools, retailer fulfilment, admin thresholds/trends; zero-result search capture).
- 3B Community Buying (group campaigns, join/leave/share, settlement, single-use group price at checkout).
- 3C Community Exchange (customer RFQs, retailer line-item bids, accept into basket).
- 3D AI Negotiator (rule-bound engine, retailer rules, quote lock-in; en/hi messages).
- 3E Dukaan vs Dukaan (90 s reverse auctions, SSE live view, award into basket).
- 3F Price Intelligence (daily ticks, lowest/highest/averages, genuine-discount & MRP-inflation badges).
- 3G Sale Stream (price drops, flash deals, hot sellers; **no Rewind**).
- 3H Bharat Multilingual (8 languages UI, Indic query normalisation, content translations, user preference).
- 3I Handwritten List to Basket (OCR provider interface, text path, review → build cart).
- Shared: `price_awards`, retailer `service_pincodes`, `basket.events.marketplace`, Phase 3 background jobs, migrations `0022`–`0030`, 53 endpoints, 12 frontend routes, opt-in live infra tests.
- Docs: FRONTEND_INTEGRATION_GUIDE.md, TEST_REPORT.md.

### Fixed
- Search returned 0 results whenever OpenSearch was unconfigured (empty mock index); now uses PostgreSQL.
- Test suite can no longer write to live Kafka/OpenSearch configured in `.env`.

### Security
- Demand unique-shopper counts resistant to guest-token inflation; non-customers cannot cast demand signals.

---

## [1.0.1-audit] — 2026-11-20 — Stabilisation audit (local branch `audit/stabilisation-and-repair`)

### Security
- Shipment create/update and return-status endpoints now require an admin (JWT + CSRF) or the internal service key. They were previously unauthenticated.
- `POST /api/v1/orders/{id}/refunds` is admin/internal only. Customers previously could self-refund delivered orders.
- Return and shipment state machines; replayed restock/refund rejected with `409`.
- CSRF enforced on orders, payments, reservations, quotes, retailer, admin and passport routers (safe methods exempt); exact localhost origin matching.
- `X-Forwarded-For` ignored unless `TRUSTED_PROXY_COUNT > 0`.
- Media URLs restricted to absolute http(s).

### Fixed
- Retailers can no longer fulfil unpaid orders; retailer cancellation restocks and refunds; order row locked during updates.
- A failed refund leaves the return in `REFUND_PENDING` instead of `REFUNDED`.
- Order is `DELIVERED` only when all its shipments are delivered; status-history `from_status` corrected.
- OpenSearch documents versioned by DB snapshot time (stock/price updates were being dropped); delete failures retried; inactive variants excluded.
- PostgreSQL search fallback: filters, totals, pagination and price sorts computed in SQL; LIKE wildcards escaped.

### Added
- `core/background.py`: starts the transactional outbox publisher (with Kafka reconnect backoff) and schedules reservation expiry, payment reconciliation and unpaid-order SLA escalation.
- `core/events/catalogue_events.py`: `product.updated` outbox events for every stock and catalogue change.
- `/ready` reports real Kafka publisher state and outbox backlog.
- Migration `0021_audit_missing_indexes` (reversible).
- Settings: `TRUSTED_PROXY_COUNT`, `BACKGROUND_WORKERS_ENABLED`, `OUTBOX_PUBLISHER_ENABLED`, `RESERVATION_CLEANUP_INTERVAL_SECONDS`, `PAYMENT_RECONCILE_INTERVAL_SECONDS`, `PAYMENT_SLA_ESCALATION_INTERVAL_SECONDS`.
- Tests: `test_audit_security_regressions.py`, `test_audit_reliability_regressions.py`, `test_audit_event_pipeline.py` (backend suite 448 → **467 passing**, 0 failed, 0 skipped).

### Changed (API contract)
- Refunds endpoint: customers now receive `403 FORBIDDEN`.
- Shipment/return-status endpoints: anonymous → `401`, non-admin → `403`, invalid transition → `409 INVALID_RETURN_TRANSITION` / `INVALID_SHIPMENT_TRANSITION`.
- Retailer order status on unpaid/cancelled orders → `409 INVALID_STATUS_TRANSITION`.
- `/internal/reservations/cleanup-expired` moved to a non-CSRF internal router (same path).

---

## [1.0.0-phase1] — 2026-11-19

### Added
- **Phase 1 Master Core Marketplace Implementation:**
  - **Demo Dataset & Seed Automation (`seed_phase1_demo.py` & `validate_phase1_demo.py`):**
    - Seeded two verified active demo retailers: `Basket Mart` (`retailer1@basket.demo`) and `Basket Lifestyle` (`retailer2@basket.demo`).
    - Seeded platform administrator (`admin@basket.demo`) and customer (`customer@basket.demo` with delivery address).
    - Seeded exactly 10 top-level canonical categories (`parent_id IS NULL`): Grocery & Food, Electronics, Fashion & Clothing, Home & Kitchen, Beauty & Personal Care, Sports & Fitness, Books & Stationery, Furniture & Decor, Automotive Accessories, Toys & Baby Products.
    - Seeded exactly 50 realistic demo products (25 for Basket Mart, 25 for Basket Lifestyle) distributed 2-3 per category, each with unique SKUs, MRPs, selling prices, GST rates (0%, 5%, 12%, 18%, 28%), HSN codes, high-resolution photography, and `store_inventory` records.
    - Automated validator confirmed 50 valid products, 50 valid retailer mappings, 50 valid category mappings, 0 orphaned products, and 0 duplicate SKUs.
  - **Retailer Module & Portal Integration:**
    - Updated retailer navigation layout strictly matching Section 8.8 (`/retailer/layout.tsx`).
    - Added custom product and listing creation backend API (`POST /api/v1/retailer/products`) and frontend form (`/retailer/listings/new`).
    - Added retailer order management (`/retailer/orders`) with line-item tenant isolation, order breakdown, and status transition actions (`CONFIRMED` -> `PROCESSING` -> `PACKED` -> `SHIPPED` -> `DELIVERED`).
    - Added retailer promotions & offers console (`/retailer/offers`, `GET/POST/PUT/DELETE /api/v1/retailer/offers`) supporting percentage and fixed-amount discounts.
    - Added retailer sales & performance analytics dashboard (`/retailer/analytics`, `GET /api/v1/retailer/analytics`) with gross sales, AOV, order status pipeline, stock health, and top selling products.
    - Added retailer operating settings console (`/retailer/settings`) with live open/close toggle, business hours, and store return policies.
  - **Customer Module & Product Comparison:**
    - Built side-by-side Product Comparison page (`/compare`) allowing customer to compare 2 to 4 products on Price, MRP, Discount %, Retailer, Stock Availability, Category, SKU, and key technical specifications.
    - Added direct "Add to Basket" action directly from comparison matrix.
    - Added comparison toggle buttons on Product Cards (`product-card.tsx`), Product Detail Page (`products/[id]/page.tsx`), and comparison badge in Header (`header.tsx`).
    - Implemented clean empty state with direct CTA to browse catalogue products.
  - **Automated Test Suite (`backend/tests/test_phase1_core_marketplace.py`):**
    - Added comprehensive automated test suite covering Test A (Retailer 1 Operations), Test B (Retailer 2 Tenant Isolation), Test C (Customer Experience), Test D (End-to-End Multi-Retailer Purchase Flow), and Test E (Admin Integration). All 5 tests passing against PostgreSQL database.

---

## [0.7.1] — 2026-11-19

### Added
- **Phase 5C.1 Marketplace Authenticity, Customer Product Visibility, Inventory Synchronization & Retailer Sales Analytics:**
  - **Marketplace Seeding & Data Authenticity:**
    - Seeded 15 authentic, verified Indian retail stores located in major cities (Bengaluru KA, Mumbai MH, Delhi DL, Hyderabad TS, Chennai TN, Pune MH, Ahmedabad GJ, Kolkata WB, Jaipur RJ, Kochi KL, Chandigarh CH, Noida UP, Gurugram HR, Indore MP, Lucknow UP) with realistic GSTINs and physical store addresses.
    - Soft-deactivated legacy artificial test retailers while safeguarding foreign-key integrity.
    - Seeded 10 core commercial categories and 77 canonical products with realistic INR pricing (e.g., MacBook Air 15" M3 ~₹1,24,900 to ₹1,27,490). Re-indexed full catalogue into OpenSearch with blue/green alias synchronization.
  - **Customer Storefront Multi-Seller Offers & Visibility:**
    - Excluded unverified, inactive, or suspended retailers from customer-facing storefront listings, faceted search results, and PDP variant listings.
    - In `ProductListingDetailSchema`, exposed `retailer_state` to power regional seller signals.
    - On Product Detail Page (`/products/[id]`), implemented interactive Multi-Seller Offer comparison cards with store name, customer rating, merchant state, stock status, MRP, selling price, and discount percentage, allowing shoppers to choose which retailer's offer to add to cart.
    - Added "Currently Unavailable" storefront state when all sellers for a product variant are unverified or inactive.
  - **Atomic Inventory Deduction & Idempotency:**
    - Guaranteed 10-minute hold on `reserved_quantity` upon reservation creation.
    - Enforced atomic permanent deduction (`on_hand_quantity -= qty`, `reserved_quantity -= qty`) upon payment confirmation (`confirm_reservation`).
    - Implemented idempotent confirmation safety: replaying confirmation on an already confirmed reservation never causes double-deductions.
    - Guaranteed that releasing expired or cancelled reservations restores `reserved_quantity` to 0 without mutating `on_hand_quantity`.
  - **Admin Retailer Directory State Filter & Store-Wise Sales Analytics:**
    - In `GET /api/v1/admin/retailers`, added multi-field `search` (name, address) and `state` filtering (e.g. `state=KA`).
    - Mounted `GET /api/v1/admin/retailers/{retailer_id}/analytics` guarded by `require_admin` calculating total completed orders, units sold, gross merchandise value (GMV), customer refunds, net sales, and per-variant sales breakdowns.
    - Built Admin Retailer Sales Analytics dashboard (`/admin/retailers/[id]`) with 4 KPI cards (Total Orders, Units Sold, GMV, Net Sales in INR), store metadata, and product-level sales breakdown table. Added direct "Analytics" action button in `/admin/retailers`.
  - **Automated Verification:**
    - Added 6 automated integration tests in `backend/tests/test_marketplace_authenticity_and_inventory.py`.
    - 390 backend tests passing (100%).
    - 68 frontend tests passing (100%).
    - Ruff backend lint: All checks passed.
    - TypeScript type check: 0 errors.
    - Next.js production build: 22/22 static pages compiled.

---

## [0.7.0] — 2026-11-19

### Added
- **Phase 5C Admin Marketplace Moderation, Retailer Approval & Platform Deals:**
  - **Alembic Migration 0014 (`0014_admin_moderation_deals`):**
    - Extended `retailers` with review audit fields: `reviewed_by_user_id` (FK `users.id`), `verified_at` (`DateTime(timezone=True)`), and `rejection_reason` (`Text`).
    - Created `retailer_verification_history` audit trail table: `id` (UUID), `retailer_id` (FK `retailers.id`), `admin_id` (FK `users.id`), `action` (VARCHAR 64), `from_status` (VARCHAR 32), `to_status` (VARCHAR 32), `reason` (Text), `created_at`.
    - Extended `discounts` with campaign targeting and limits: `scope` (VARCHAR 32, default `'PLATFORM_WIDE'`), `category_id` (FK `categories.id`), `product_id` (FK `products.id`), `usage_limit` (Integer), `times_used` (Integer, default 0), and `description` (Text). Verified clean upgrade and downgrade round-trip.
  - **Admin Canonical Catalogue Management:**
    - Mounted `GET /api/v1/admin/catalogue/products`, `POST /api/v1/admin/catalogue/products`, `GET /api/v1/admin/catalogue/products/{id}`, `PUT /api/v1/admin/catalogue/products/{id}`, and `DELETE /api/v1/admin/catalogue/products/{id}`.
    - Mounted variant management: `POST /api/v1/admin/catalogue/products/{id}/variants`, `PUT /api/v1/admin/catalogue/variants/{id}`, and `DELETE /api/v1/admin/catalogue/variants/{id}`.
    - Mounted category endpoints: `GET /api/v1/admin/catalogue/categories` and `POST /api/v1/admin/catalogue/categories`.
    - **Canonical Blueprint Invariant:** Guaranteed that editing canonical master products, attributes, or variants never alters individual retailer listing prices or merchant inventory.
  - **Retailer Verification & Compliance Desk:**
    - Mounted `GET /api/v1/admin/retailers/{id}` returning store details, submitted compliance documents, and verification audit history.
    - Mounted `POST /api/v1/admin/retailers/{id}/verify` and `POST /api/v1/admin/retailers/{id}/documents/{doc_id}/verify` persisting reviewer identity, decision, timestamp, and audit notes.
    - **Verification Enforcement:** `RetailerService` strictly prevents unverified (`PENDING`), `REJECTED`, or `SUSPENDED` retailers from publishing listings, updating prices, or adjusting warehouse inventory.
  - **Platform Deals & Promotion Scheduler:**
    - Mounted `GET /api/v1/admin/deals`, `POST /api/v1/admin/deals`, `GET /api/v1/admin/deals/{id}`, `PUT /api/v1/admin/deals/{id}`, and `DELETE /api/v1/admin/deals/{id}`.
    - Supported scopes (`PLATFORM_WIDE`, `CATEGORY`, `PRODUCT`, `LISTING`), discount types (`PERCENTAGE` up to 90%, `FIXED_AMOUNT`), min order thresholds, max discount caps, usage limits, and scheduling (`valid_from`, `valid_to`).
    - **Pricing Integrity Invariant:** Deals apply dynamically in checkout quotes without modifying underlying retailer listing selling prices.
  - **Frontend Admin Consoles:**
    - `/admin/layout.tsx`: Refined operations desk sidebar with active tab tracking and direct navigation.
    - `/admin/page.tsx`: Quick module launch cards for Retailers & Verification, Platform Catalogue, and Deals & Promotions.
    - `/admin/retailers/page.tsx`: Full retailer verification console with status filter tabs, search, document preview & verification, and decision modal with audit logging.
    - `/admin/catalogue/page.tsx`: Canonical catalogue manager with search, category filtering, product create/edit modals, and variant hierarchy manager.
    - `/admin/deals/page.tsx`: Platform deals dashboard with status filtering, deal cards, active toggles, and deal create/edit modals.
  - **Automated Verification:**
    - Added 5 test suites in `tests/test_admin_marketplace_moderation.py` covering Admin RBAC, canonical catalogue isolation, retailer approval enforcement, platform deals scheduling, and scoped deals usage limits. All 384 backend tests passed.
    - Added 5 API client integration test suites in `portals.test.ts`. All 68 frontend tests passed. Zero TypeScript errors and production Next.js build verified.

---

## [0.6.1] — 2026-11-19

### Added
- **Phase 5B Retailer Store Listings, Variant Pricing & Inventory Management:**
  - **Alembic Migration 0013 (`0013_retailer_inventory`):** Added `low_stock_threshold` (`INTEGER`, default 10, non-negative check constraint) to `store_inventory`.
  - **Catalogue Variant Lookup:** Mounted `GET /api/v1/retailer/catalogue/products` for authenticated retailers to browse canonical products and variants with automatic deduplication (`is_already_listed`, `existing_listing_id`).
  - **Store Listings CRUD & Strict Anti-IDOR:** Mounted `GET /api/v1/retailer/listings`, `POST /api/v1/retailer/listings`, `GET /api/v1/retailer/listings/{id}`, `PUT /api/v1/retailer/listings/{id}`, and `DELETE /api/v1/retailer/listings/{id}`. Identity is cryptographically derived from the authenticated JWT session; cross-tenant access returns HTTP 404.
  - **Variant Pricing Rules & MRP Invariants:** Independent retailer pricing per variant with strict validation enforcing `selling_price <= original_price` (`INVALID_PRICING`), without mutating canonical catalogue product data.
  - **Warehouse Inventory Console & Concurrency Protection:** Mounted `GET /api/v1/retailer/inventory`, `POST /api/v1/retailer/listings/{id}/inventory`, and `POST /api/v1/retailer/inventory/bulk-adjust`. All adjustments use `SELECT ... FOR UPDATE` row locks, enforce non-negative stock invariants, and forbid reducing on-hand inventory below active customer holds (`CANNOT_REDUCE_BELOW_RESERVED`).
  - **Low-Stock Alerting:** Configurable `low_stock_threshold` triggers dynamic `is_low_stock` flags, inventory dashboard filters, and warning alerts on the retailer overview console.
  - **Frontend Pages & Consoles:** Implemented `/retailer/listings` (filter/search table and price edit modal), `/retailer/listings/new` (canonical product/variant picker), and `/retailer/inventory` (warehouse stock console with 6 KPI summary cards, filter tabs, and SET/DELTA stock adjustment modals).
  - **Automated Verification:** Added 7 comprehensive tests in `test_retailer_listings_inventory.py` covering RBAC, catalogue lookup, listing creation, anti-IDOR isolation, pricing hierarchies, customer hold safety, and concurrent race condition protections. Added 4 unit test suites in `portals.test.ts`. Full backend (379 tests) and frontend (67 tests) suites green.

---

## [0.6.0] — 2026-11-19

### Added
- **Phase 5A Multi-Role Portals & RBAC Foundation:**
  - **Alembic Migration 0012 (`0012_multi_role_portals`):** Extended `retailers` table with unique `user_id` foreign key referencing `users.id`, `business_address`, `contact_phone`, `contact_email`, `business_hours` (JSONB), `policies` (JSONB), `is_open`, and `verification_status` (`PENDING`, `VERIFIED`, `SUSPENDED`). Created `retailer_verification_documents` table with foreign key to `retailers.id`.
  - **Server-Side Authorization & Tenancy Isolation:** Created `require_admin`, `require_retailer`, and `get_current_retailer` dependencies in `app.modules.identity.dependencies`. Tenant boundary is strictly isolated via JWT session extraction, preventing cross-tenant data leakage or spoofing. Role self-promotion is blocked via role immutability.
  - **Merchant Registration Endpoint:** Added `POST /api/v1/auth/retailer/register` for atomic creation of retailer user accounts and store records with automatic slug disambiguation.
  - **Admin Management APIs:** Added `GET /api/v1/admin/overview`, `GET /api/v1/admin/retailers`, and `POST /api/v1/admin/retailers/{retailer_id}/verify` for onboarding review and status updates.
  - **Retailer Profile & Overview APIs:** Added `GET /api/v1/retailer/profile`, `PUT /api/v1/retailer/profile`, and `GET /api/v1/retailer/overview`.
  - **Frontend Portals & Layouts:** Built `/admin` (overview KPIs, retailer onboarding verification queue), `/retailer` (store dashboard, quick metrics, live open/closed toggle), `/retailer/profile` (store settings), and `/register/retailer` (onboarding form). Role guards enforce strict access redirection or 403 Forbidden states.
  - **Role-Based Navigation:** Added dynamic role links (`Admin Portal` for admins, `Retailer Portal` for retailers, "Sell on BASKET" CTA for customers) to header and mobile drawer.
- **Hardened Checkout Reservation Derivation:**
  - Reinforced server-authoritative `quote_id` derivation from inventory reservations in `OrderService.create_order`.
  - Enforced strict ownership validation (anti-IDOR), status validation (`ACTIVE` only, rejecting `CONFIRMED`, `EXPIRED`, `RELEASED`), server UTC expiry checks, and quote association validation before resolving `effective_quote_id`.
  - Added 5 negative tests in `test_orders.py` covering arbitrary, foreign-owned, expired, released, and unassociated reservations.

---

## [0.5.0] — 2026-11-19

### Added
- **Phase 4 Post-Purchase Experience (PR #17):**
  - **7-Stage Order Progress Tracker:** Order Placed $\rightarrow$ Confirmed $\rightarrow$ Processing $\rightarrow$ Packed $\rightarrow$ Shipped $\rightarrow$ Out for Delivery $\rightarrow$ Delivered (`/orders/[id]/track`).
  - **Order History & Management (`/orders`):** Authenticated customer order listing with status filtering, date range queries, and order number search.
  - **Guest Order Lookup (`/orders`):** Secure, unguessable guest access tokens (`gat_...`) for non-authenticated tracking.
  - **Shipments & Consignments:** Multi-shipment consignment tracking with carrier codes, tracking numbers, and external URLs.
  - **Order Cancellations:** Pre-dispatch cancellation workflow with reason recording, inventory release, and automatic refund triggering.
  - **Order Returns & Inspections:** Post-delivery return requests with line-item quantity selection, reason codes, condition grade inspection, restock approval, and refund computation.
  - **In-App Customer Notifications:** Event-driven notification center with unread counters and read status tracking.
  - **Alembic Migration 0011:** Created `order_status_history`, `shipments`, `shipment_items`, `order_returns`, `return_items`, `return_status_history`, and `customer_notifications`.
- **Order Visibility & Navigation Fix (PR #18):**
  - Added "My Orders" Quick Action card and "Recent Purchases" list to `/account`.
  - Added explicit "My Orders" button to the checkout confirmation page.
  - Added client-side empty state and sign-in CTA on `/orders` when visitors are unauthenticated, preventing spurious 401 request errors.
  - Made `quote_id` optional in `CreateOrderRequest` schema with automatic server-authoritative derivation from inventory reservations in PostgreSQL.
  - Added full regression test suite verifying customer order visibility, logout/login persistence, and anti-IDOR isolation (`test_orders_postpurchase.py`).

---

## [0.4.1] — 2026-11-19

### Changed
- **Aiven Kafka SASL_SSL Configuration (PR #16):**
  - Configured Aiven Kafka `SASL_SSL` protocol and `SCRAM-SHA-256` mechanism using `infra/aiven/certs/ca.pem`.
  - Replaced hardcoded local certificate dependencies in test suite with temporary directory PEM fixtures for 100% portable CI execution.
- **Genuine Razorpay Sandbox API Separation (PR #15):**
  - Enforced strict separation between local cryptographic HMAC test simulations and genuine Razorpay test mode transactions.
  - Banned direct database state manipulation to fake provider captures. Real sandbox transactions require authentic `rzp_test_...` merchant keys.

---

## [0.4.0] — 2026-11-18

### Added
- **Phase 3D–F Search & Observability (PR #13, PR #14):**
  - **Aiven OpenSearch Integration:** Versioned indices (`basket_products_v1`) with blue/green alias routing (`basket_products_search`, `basket_products_write`).
  - **Asynchronous Search Indexer Consumer:** Consumes catalogue events from Kafka and projects documents into OpenSearch using `external_gte` versioning.
  - **Search Circuit Breaker:** 3-state state machine (`CLOSED`, `OPEN`, `HALF_OPEN`) preventing cascading latency during cluster degradation.
  - **PostgreSQL Full-Text Search Fallback:** Transparent SQL search fallback using `tsvector` matching over canonical product attributes when OpenSearch is unavailable.
  - **Prometheus Metrics Exposition:** Thread-safe metrics registry exposing standard Prometheus 0.0.4 text format at `GET /metrics`.
  - **Grafana Dashboard:** Pre-configured dashboard in `deploy/observability/dashboards/basket-platform.json`.

---

## [0.3.0] — 2026-11-18

### Added
- **Phase 3A–C Event Streaming & Reliability (PR #9, PR #10, PR #11, PR #12):**
  - **Standardized Domain Event Envelopes:** Pydantic event schemas for `order.created`, `order.confirmed`, `order.cancelled`, `inventory.reserved`, `payment.captured`.
  - **Transactional Outbox Publisher Daemon:** Lease-fenced background publisher querying `outbox_events` with `SELECT ... FOR UPDATE SKIP LOCKED` (`0009_outbox_lease.py`).
  - **Consumer Reliability & Deduplication:** `consumer_inbox` table (`0010_consumer_inbox.py`) enforcing exactly-once side-effect execution across consumer groups.
  - **Dead Letter Queue (DLQ):** Unhandled consumer errors route to DLQ after exponential backoff exhaustion.

---

## [0.2.0] — 2026-11-17

### Added
- **Phase 2 Commerce Pipeline (PR #3, PR #4, PR #5, PR #6, PR #7, PR #8):**
  - **Identity & Sessions (Phase 2A):** Argon2id password hashing, HTTP-only JWT cookies, Double-Submit CSRF, customer addresses with auto-promote default trigger (`0003_identity_schema`).
  - **Persistent Shopping Cart (Phase 2B):** Guest session carts, authenticated carts, and automated cart merging on login (`0004_cart_schema`).
  - **Pricing Quotes & Discounts (Phase 2C):** Platform/retailer discounts, multi-item tax breakdowns (CGST/SGST/IGST), HMAC-SHA256 signed quotes with 5m expiry (`0005_pricing_quotes_schema`).
  - **Inventory Reservations (Phase 2D):** All-or-nothing atomic stock locking using sorted row locks (`SELECT ... FOR UPDATE`), 10-minute configurable reservation expiry (`0006_inventory_reservations_schema`).
  - **Orders & Outbox (Phase 2E):** Order state machine, immutable purchased-item snapshots, atomic transactional outbox insertion (`0007_orders_outbox_schema`).
  - **Payment Gateway (Phase 2F):** Dual-mode Razorpay sandbox client, server-side capture verification, HMAC webhook signatures, trigger-protected immutable captures (`0008_payments_razorpay_schema`).

---

## [0.1.0] — 2026-11-16

### Added
- **Phase 1 Catalogue & Storefront Foundation (PR #2):**
  - Canonical product catalogue, categories, variants, retailers, stores, listings, prices, and store inventory (`0002_catalogue_schema`).
  - Multi-category storefront browsing, product detail view, and responsive product grids in Next.js 15.

---

## [0.0.1] — 2026-11-16

### Added
- **Phase 0 Monorepo Foundation (PR #1):**
  - Monorepo directory structure: `frontend/` (Next.js 15 App Router) and `backend/` (FastAPI modular monolith).
  - SQLAlchemy 2.0 async engine and initial Alembic baseline marker (`0001_initial_baseline.py`).
  - Structured JSON logging, global exception handling, and request ID tracing.
  - Health probes (`/health`, `/ready`).
  - Automated bootstrap (`scripts/dev-setup.sh`) and verification (`scripts/verify-environment.sh`) scripts.
