# BASKET — Implementation Status & Verification Audit

> **Status:** Code-Verified Implementation Status  
> **Target Audience:** Engineering Leads, QA Inspectors, and System Auditors  
> **Last Audited:** 2026-11-19T22:55:00+05:30  
> **Base Branch:** `integration` (commit `615a4c5`)  
> **Current Feature Branch:** `feature/phase1-master-core-marketplace`  
> **Head Status:** Single Alembic head `0014_admin_moderation_deals`  
> **Test Status:** 395 Backend Tests Passed (100%), 68 Frontend Tests Passed (100%), CI Green  

---

## 1. Executive Summary

This document provides a verified, evidence-backed audit of the current BASKET repository implementation. It cross-references every subsystem against actual source code, database migrations, automated tests, Git history, and Pull Requests merged into `integration`.

The finalized product specification (including multi-role Admin, Retailer, and AI features) is maintained separately in [`FEATURE_SPECIFICATION.md`](FEATURE_SPECIFICATION.md). This document reports strictly on what is **actually implemented, operational, and tested in the codebase today**.

---

## 2. Pull Request & Milestone History

All core features and fixes have been merged into `integration` through clean, reviewed pull requests:

| PR # | Branch Name | Title / Purpose | Merge Commit | Test Count | Key Implemented Capabilities |
|:---:|:---|:---|:---:|:---:|:---|
| **#1** | `feature/phase0-foundation` | Phase 0 Monorepo Baseline | `db9d790` | 12 backend / 7 frontend | FastAPI shell, Next.js 15, logging, exceptions, health probes. |
| **#2** | `feature/phase1-catalogue-storefront` | Phase 1 Catalogue & Storefront Foundation | `f58c7e9` | 32 backend / 14 frontend | Products, categories, variants, retailers, listings, prices, inventory. |
| **#3** | `feature/phase2-identity-addresses` | Phase 2A Identity & Addresses | `e0971b3` | 58 backend / 21 frontend | Argon2id, JWT cookies, double-submit CSRF, address auto-promote. |
| **#4** | `feature/phase2-persistent-cart` | Phase 2B Persistent Cart | `a1b94e2` | 76 backend / 28 frontend | Guest/user carts, cart item mutations, guest-to-user cart merge. |
| **#5** | `feature/phase2-pricing-quotes` | Phase 2C Pricing Quotes & Discounts | `f87d412` | 104 backend / 34 frontend | Multi-item discounts, GST computation, HMAC quotes (5m expiry). |
| **#6** | `feature/phase2-inventory-reservations` | Phase 2D Inventory Reservations | `e382d54` | 129 backend / 40 frontend | All-or-nothing stock locking, row-level locks, 10m expiry. |
| **#7** | `feature/phase2-orders-outbox` | Phase 2E Orders & Transactional Outbox | `d9120e7` | 162 backend / 48 frontend | Orders state machine, immutable snapshots, outbox persistence. |
| **#8** | `feature/phase2-payment-gateway` | Phase 2F Payment Gateway Integration | `b491ec8` | 205 backend / 54 frontend | Dual-mode Razorpay sandbox, server verification, HMAC webhooks. |
| **#9** | `feature/phase3-event-streaming-contracts`| Phase 3A Event Streaming Contracts | `c019d38` | 238 backend / 54 frontend | Standardized event envelopes, Pydantic schemas, Kafka producer. |
| **#10** | `feature/phase3-outbox-publisher` | Phase 3B Outbox Publisher Daemon | `882ab19` | 274 backend / 54 frontend | `FOR UPDATE SKIP LOCKED` leases, background publisher worker. |
| **#11** | `feature/phase3-consumer-reliability` | Phase 3C Consumer Reliability & Inbox | `e491fa3` | 316 backend / 54 frontend | `consumer_inbox` deduplication, idempotent retries, DLQ routing. |
| **#12** | `main` | Sync main into integration | `61f89bc` | 316 backend / 54 frontend | Clean synchronisation baseline. |
| **#13** | `feature/phase3-search-observability` | Phase 3D-F Search & Observability | `449a01f` | 338 backend / 60 frontend | OpenSearch indexing, search circuit breaker, SQL fallback, metrics. |
| **#14** | `feature/launch-readiness-sandbox` | Launch Readiness Sandbox | `5719ab2` | 338 backend / 60 frontend | E2E sandbox journey rehearsal and verification gates. |
| **#15** | `feature/sandbox-deployment-production-readiness` | Production Readiness & Real Razorpay Split | `c90eb03` | 344 backend / 60 frontend | Strict separation of mock vs real Razorpay sandbox API calls. |
| **#16** | `feature/external-integration-config-repair` | External Config Repair & Portability | `099b115` | 348 backend / 60 frontend | Kafka SASL_SSL setup, temporary CA PEM fixtures for CI portability. |
| **#17** | `feature/phase4-orders-postpurchase` | Phase 4 Orders, Tracking, Returns | `1193aa9` | 352 backend / 63 frontend | Order tracking (7 stages), cancellations, returns, notifications. |
| **#18** | `fix/order-visibility-after-checkout` | Post-Checkout Visibility & Navigation Fix | `16a3003` | 361 backend / 63 frontend | Resolved post-checkout order visibility, `/account` recent purchases, `/orders` unauthenticated handling, and `quote_id` schema flexibility. |
| **#20** | `feature/phase5-multi-role-rbac-foundation` | Phase 5A RBAC Foundation | `8392fb9` | 368 backend / 63 frontend | Customer, Retailer, Admin RBAC; portal route security; checkout quote_id resolution. |
| **#21** | `feature/phase5b-retailer-catalogue-inventory` | Phase 5B Retailer Listings & Inventory | `cd7e38b` | 378 backend / 68 frontend | Retailer listings CRUD, independent variant pricing, tenant inventory management. |
| **#22** | `feature/phase5c-admin-marketplace-moderation` | Phase 5C Admin Moderation & Deals | `cd7e38b` | 384 backend / 68 frontend | Admin catalogue moderation, retailer verification workflow, platform deals. |
| **#23** | `feature/phase5c1-authentic-marketplace` | Phase 5C.1 Authentic Marketplace | `615a4c5` | 390 backend / 68 frontend | Multi-seller storefront offers, atomic inventory hold/deduction, sales analytics. |
| **#24** | `feature/phase1-master-core-marketplace` | Phase 1 Master Core Marketplace | *Current* | 395 backend / 68 frontend | 2 demo retailers, 10 top-level categories, 50 products, product comparison (`/compare`), retailer orders/offers/analytics/settings, E2E flow. |

---

## 3. Detailed Component Implementation Audit

### 3.1 Identity, Authentication & Security
- **Source Files:** `backend/app/modules/identity/` (router, service, repository, security, schemas).
- **Authentication Scheme:** Stateful session tracking via `user_sessions` with Argon2id password hashing (`$argon2id$v=19$m=65536,t=3,p=4`).
- **Token Management:** Short-lived access JWTs (15 min) and rolling refresh tokens (7 days). Tokens delivered via secure HTTP-only cookies (`access_token`, `refresh_token`).
- **CSRF Defense:** Double-Submit Cookie pattern. Server issues un-HttpOnly `XSRF-TOKEN` cookie; mutating requests (`POST`, `PATCH`, `DELETE`) require matching `X-CSRF-Token` header. Bearer token requests exempt.
- **Customer Addresses:** Multi-address support with PostgreSQL trigger automatically promoting the first created address or single remaining address to `is_default=True`.
- **Database Tables:** `users`, `user_sessions`, `customer_addresses`.
- **Verified Capabilities:** Registration, login, logout, multi-device logout-all, refresh rotation, address CRUD, anti-IDOR address ownership isolation.

### 3.2 Catalogue & Storefront
- **Source Files:** `backend/app/modules/catalogue/`, `frontend/app/products/`, `frontend/app/categories/`.
- **Architecture:** Hierarchical categories (L1/L2), canonical products, variant dimension attributes (size, color, pack, storage), retailer listings, price history, and store-level inventory.
- **Database Tables:** `categories`, `products`, `product_variants`, `retailers`, `stores`, `retailer_listings`, `prices`, `store_inventory`.
- **Verified Capabilities:** Multi-category browsing, variant selection, price/stock display, stock reservation indicators, SEO-friendly SSR pages in Next.js 15.

### 3.3 Shopping Cart
- **Source Files:** `backend/app/modules/cart/`, `frontend/app/cart/`.
- **Architecture:** Universal persistent cart supporting both guest visitors (session token) and authenticated customers.
- **Cart Merge Algorithm:** When a guest logs in or registers, `POST /api/v1/cart/merge` safely combines guest cart items into the user's permanent cart, revalidating current stock and clamping quantities to store availability.
- **Database Tables:** `carts`, `cart_items`.
- **Verified Capabilities:** Add to cart, update quantity, remove item, clear cart, automated guest-to-customer cart merge with stock safety.

### 3.4 Pricing, Discounts & Quotes
- **Source Files:** `backend/app/modules/pricing/`.
- **Architecture:** Server-authoritative checkout quote construction. Calculates line-item base price, platform/retailer discounts, intra-state CGST/SGST vs inter-state IGST, and shipping fees.
- **Cryptographic Quotes:** Quotes are HMAC-SHA256 signed with a strict 5-minute validity window. Modifying item quantities, prices, or address invalidates the signature and rejects checkout.
- **Database Tables:** `discounts`, `retailer_discounts`, `checkout_quotes`, `checkout_quote_items`.
- **Verified Capabilities:** Multi-item tax breakdown, coupon/discount validation, HMAC signature tampering rejection, quote expiration.

### 3.5 Inventory Reservations & Concurrency Protection
- **Source Files:** `backend/app/modules/inventory/`.
- **Architecture:** All-or-nothing atomic inventory locking. When checkout is initiated, stock is locked in `store_inventory` using sorted row locks (`SELECT ... FOR UPDATE ORDER BY listing_id`) to prevent concurrency deadlocks.
- **Reservation Lifespan:** Expiring reservation window (10 minutes). An automated expiry/reconciliation job releases held stock if payment is not confirmed within the window.
- **Database Tables:** `inventory_reservations`, `inventory_reservation_items`.
- **Verified Capabilities:** Concurrent checkout race condition safety ("Sale Storm"), dead-stock prevention, automatic stock release upon reservation expiry.

### 3.6 Orders & Transactional Outbox
- **Source Files:** `backend/app/modules/orders/`, `backend/app/events/`.
- **Architecture:** Order creation commits the order, immutable item snapshots (capturing product title, variant title, seller name, HSN code, GST rate, unit price), delivery address snapshot, and transactional outbox event in **a single atomic PostgreSQL transaction**.
- **State Machine:** `PENDING_PAYMENT` $\rightarrow$ `CONFIRMED` $\rightarrow$ `PROCESSING` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` $\rightarrow$ `OUT_FOR_DELIVERY` $\rightarrow$ `DELIVERED` (or `CANCELLED` / `REFUNDED`).
- **Database Tables:** `orders`, `order_items`, `order_status_history`, `outbox_events`.
- **Verified Capabilities:** Atomic creation, immutable purchased item snapshots, outbox event persistence, idempotent order submission via `Idempotency-Key`.

### 3.7 Payment Gateway & Razorpay Sandbox Verification
- **Source Files:** `backend/app/modules/payments/`.
- **Dual-Mode Integration:**
  1. **Local Cryptographic Engine:** Full local test simulation using cryptographically valid HMAC signatures without requiring live external network access.
  2. **Authentic Razorpay Sandbox:** Genuine test mode using `RAZORPAY_KEY_ID` (`rzp_test_...`) and `RAZORPAY_KEY_SECRET`. Creates genuine Razorpay orders (`order_...`) and captures test payments (`pay_...`).
- **Webhook Ingestion:** Idempotent webhook handler verifying `X-Razorpay-Signature`. Duplicate webhooks are safely ignored (`reason="ALREADY_INGESTED"`). Tampered signatures return HTTP 400.
- **Database Triggers:** Immutable payment capture facts in `payment_captures` enforced by database triggers; prevents retroactively modifying financial ledger entries.
- **Database Tables:** `payments`, `payment_captures`, `payment_refunds`, `webhook_events`.
- **Verified Capabilities:** Server-side signature verification, capture verification, duplicate webhook deduplication, partial/full refund flows, auto-refund on anomalous double-captures.

### 3.8 Asynchronous Event Streaming (Kafka & Outbox Publisher)
- **Source Files:** `backend/app/events/publisher.py`, `backend/app/core/consumer/`.
- **Publisher Architecture:** Background worker querying `outbox_events` using `SELECT ... FOR UPDATE SKIP LOCKED` with durable leases (`lease_id`, `lease_expires_at`). Marks rows `published=True` only after Kafka broker ACK.
- **Kafka Security:** Aiven Kafka configured using `SASL_SSL` protocol and `SCRAM-SHA-256` mechanism with `infra/aiven/certs/ca.pem`.
- **Consumer Reliability:** Consumers enforce idempotent processing via `consumer_inbox` table with unique constraint `(consumer_group, event_id)`. Unhandled errors transition through exponential backoff to a Dead Letter Queue (DLQ).
- **Database Tables:** `outbox_events`, `consumer_inbox`.
- **Verified Capabilities:** Zero duplicate event side-effects, outbox publisher lease recovery, DLQ routing, CI test portability with temporary PEM certificate fixtures.

### 3.9 Search Engine & Resilience Circuit Breaker
- **Source Files:** `backend/app/core/search/`, `backend/app/modules/search/`, `frontend/app/search/`.
- **OpenSearch Integration:** Derived search index (`basket_products_v1`) with blue/green alias routing (`basket_products_search`, `basket_products_write`). Indexed via asynchronous Kafka catalogue consumers with `external_gte` versioning.
- **Search Circuit Breaker:** 3-state state machine (`CLOSED`, `OPEN`, `HALF_OPEN`). After 5 consecutive OpenSearch failures, trips to `OPEN` and fast-fails queries directly to PostgreSQL without network timeouts.
- **PostgreSQL FTS Fallback:** When OpenSearch is down or circuit is open, search transparently executes against PostgreSQL using `tsvector` full-text search across product name, brand, description, and category.
- **Verified Capabilities:** Multi-faceted search (categories, brands, price ranges), sorting (relevance, price asc/desc, newest), instant search suggestions, transparent circuit breaker failover and recovery.

### 3.10 Post-Purchase Experience, Tracking & Returns (Phase 4)
- **Source Files:** `backend/app/modules/orders/` (router, service, repository, schemas), `frontend/app/orders/`, `frontend/app/account/`.
- **Order Tracking:** 7-stage lifecycle stepper: Order Placed $\rightarrow$ Confirmed $\rightarrow$ Processing $\rightarrow$ Packed $\rightarrow$ Shipped $\rightarrow$ Out for Delivery $\rightarrow$ Delivered.
- **Shipments & Consignments:** Multi-shipment consignment tracking with carrier codes, tracking numbers, and external tracking URLs.
- **Cancellations:** Customer-initiated cancellation allowed prior to dispatch (`PENDING_PAYMENT`, `CONFIRMED`, `PROCESSING`), triggering automatic stock release and refund initiation.
- **Returns & Refunds:** Post-delivery return requests with line-item selection, quantity, reason, condition inspection, and refund computation.
- **Guest Order Lookup:** Unguessable cryptographically random guest access tokens (`gat_...`) allowing guest purchasers to securely track orders without authenticating or accessing other customers' data.
- **Customer Notification Center:** Event-driven in-app notifications (`ORDER_CONFIRMED`, `SHIPMENT_DISPATCHED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `REFUND_PROCESSED`).
- **Database Tables:** `order_status_history`, `shipments`, `shipment_items`, `order_returns`, `return_items`, `return_status_history`, `customer_notifications`.
- **Verified Capabilities:** Full 7-stage tracking UI, cancellation workflows, return creation and inspection, guest order lookup, unread notification badges.

---

## 4. Phase 4 Order Visibility & Navigation Issue — Root Cause & Resolution

During Phase 4 testing, a critical issue was observed where customers completed checkout and reached the "Payment Verified & Order Confirmed!" screen, but placed orders were not immediately visible.

### 4.1 Root Cause Breakdown
1. **Stale Running Server:** The background Next.js server was running a pre-Phase 4 build compiled before `/orders` routes existed, resulting in `HTTP 404 Not Found` when navigating to `/orders`.
2. **Old Checkout Button Destination:** The pre-Phase 4 checkout success button ("View My Orders") navigated to `/account`, which previously contained only user profile and addresses without a purchase history section.
3. **Missing Account Purchases:** The `/account` view only rendered user profile details and addresses without exposing a customer's placed orders or direct links to order details and tracking.
4. **401 Unauthenticated Error on Orders Page:** In `frontend/app/orders/page.tsx`, `fetchOrders()` was triggered unconditionally when `!authLoading`, firing an unauthenticated `GET /api/v1/orders` and displaying a red 401 error banner for guest visitors instead of an empty state and sign-in prompt.
5. **Checkout Payload Validation (`quote_id`):** In `backend/app/modules/orders/schemas.py`, `CreateOrderRequest` previously declared `quote_id: uuid.UUID` as mandatory. When checkout was opened via `/checkout?reservation_id=<id>` without `&quote_id=...`, the request failed with HTTP 422: `The request payload validation failed: quote_id: Field required`.

### 4.2 Implemented Corrections (PR #18, Commits `01d7e73` and `e734c64`)
- **Backend Schema:** In `backend/app/modules/orders/schemas.py`, updated `CreateOrderRequest` to `quote_id: uuid.UUID | None = None` and added empty string normalization. In `OrderService.create_order`, if `quote_id` is omitted, it is derived server-authoritatively from the inventory reservation in PostgreSQL.
- **Frontend Orders Page:** In `frontend/app/orders/page.tsx`, conditioned `fetchOrders()` on `isAuthenticated`. Unauthenticated visitors see an inviting empty state prompting sign-in or guest lookup without firing 401 requests.
- **Account Page:** In `frontend/app/account/page.tsx`, added "My Orders" to the Quick Actions Grid and added a "Recent Purchases" list displaying recent orders with status badges, prices, and direct buttons to **Details** and **Track**.
- **Checkout Page:** In `frontend/app/checkout/page.tsx`, added direct "My Orders" navigation action alongside "View Order Details" and "Track Order".
- **Regression Tests:** Added tests in `backend/tests/test_orders_postpurchase.py` verifying customer order visibility, logout/login persistence, anti-IDOR isolation, and idempotent order creation.
- **Browser Subagent E2E Verification:** Visually verified `/account`, `/orders`, `/orders/[id]`, and `/orders/[id]/track` with live screenshots in the browser.

### 4.3 Phase 5A Multi-Role Portals & RBAC Foundation + Hardened Checkout Derivation
- **Alembic Migration 0012 (`0012_multi_role_portals`):** Added `user_id` FK (unique, indexed) to `retailers`, plus business address, contact phone/email, business hours (JSONB), policies (JSONB), `is_open`, and `verification_status` (`PENDING`, `VERIFIED`, `SUSPENDED`). Created `retailer_verification_documents` table. Verified clean upgrade and downgrade.
- **Server-Side RBAC Enforcement:** Implemented `require_admin`, `require_retailer`, and `get_current_retailer` dependencies in `app.modules.identity.dependencies`. Retailer tenant data isolation is cryptographically verified from the authenticated user's JWT session; retailers can never access or modify another retailer's store profile or metrics. Prevented self-promotion by enforcing role immutability.
- **Merchant Onboarding & Admin Moderation:** Mounted `POST /api/v1/auth/retailer/register` for atomic user + retailer creation. Mounted Admin endpoints (`GET /api/v1/admin/overview`, `GET /api/v1/admin/retailers`, `POST /api/v1/admin/retailers/{id}/verify`) and Retailer endpoints (`GET /api/v1/retailer/profile`, `PUT /api/v1/retailer/profile`, `GET /api/v1/retailer/overview`).
- **Frontend Role Portals:** Built `/admin` (overview KPIs, retailer onboarding verification queue), `/retailer` (store dashboard, quick metrics, live open/closed toggle), `/retailer/profile` (store settings), and `/register/retailer` (onboarding form). Role guards enforce strict access redirection or 403 Forbidden states.
- **Hardened Checkout Reservation Derivation:** In `backend/app/modules/orders/service.py`, reinforced server-authoritative `quote_id` derivation from inventory reservations. The derivation strictly validates reservation ownership (anti-IDOR), status (`ACTIVE` only, rejecting `CONFIRMED`, `EXPIRED`, `RELEASED`), server UTC expiry, and quote association before resolving `effective_quote_id`. Added 5 negative tests in `test_orders.py` verifying all failure scenarios.

### 4.4 Phase 5B Retailer Store Listings, Variant Pricing & Inventory Management
- **Alembic Migration 0013 (`0013_retailer_inventory`):** Added `low_stock_threshold` (`INTEGER`, default 10, non-negative check constraint) to `store_inventory`. Verified clean downgrade to `0012_multi_role_portals` and upgrade back to `0013_retailer_inventory`.
- **Catalogue Variant Browsing & Deduplication:** Mounted `GET /api/v1/retailer/catalogue/products` allowing verified retailers to search canonical products and select variants, automatically detecting if the variant is already listed (`is_already_listed`, `existing_listing_id`).
- **Store Listings CRUD & Strict Anti-IDOR:** Mounted `GET /api/v1/retailer/listings`, `POST /api/v1/retailer/listings`, `GET /api/v1/retailer/listings/{id}`, `PUT /api/v1/retailer/listings/{id}`, and `DELETE /api/v1/retailer/listings/{id}`. The backend derives `retailer_id` exclusively from the authenticated session; client-supplied retailer IDs are never accepted. Negative isolation tests prove Retailer A cannot read, update, delete, or adjust inventory for Retailer B's listings (HTTP 404).
- **Variant Pricing Rules & MRP Invariants:** Retailers set independent original price (MRP) and selling price per variant. Pydantic validators and service business rules enforce `selling_price <= original_price` (`INVALID_PRICING`), preventing accidental or fraudulent negative discounts.
- **Warehouse Stock Management & Concurrency Protection:** Mounted `GET /api/v1/retailer/inventory`, `POST /api/v1/retailer/listings/{id}/inventory`, and `POST /api/v1/retailer/inventory/bulk-adjust`. All inventory mutations acquire `SELECT ... FOR UPDATE` row locks. Adjustments support `SET` and `DELTA` types, enforce database-backed non-negative stock invariants, and forbid reducing on-hand stock below active customer reservation holds (`CANNOT_REDUCE_BELOW_RESERVED`). Parallel async race tests prove concurrent decrements cannot oversubscribe inventory or cause lost updates.
- **Low-Stock Alerting:** Configurable `low_stock_threshold` triggers real-time `is_low_stock` state flags in database queries, powering the warning banner in `/retailer` and dedicated `LOW_STOCK` filter tabs in the inventory console.
- **Frontend Consoles:** Implemented `/retailer/listings` (listings table with search and pricing edit modal), `/retailer/listings/new` (catalogue explorer with live variant preview), and `/retailer/inventory` (warehouse console with 6 KPI cards, status filters, and stock adjustment modal).

### 4.5 Phase 5C Admin Marketplace Moderation, Retailer Approval & Platform Deals
- **Alembic Migration 0014 (`0014_admin_moderation_deals`):**
  - Added review audit columns to `retailers`: `reviewed_by_user_id` (FK `users.id`), `verified_at` (`DateTime(timezone=True)`), `rejection_reason` (`Text`).
  - Created `retailer_verification_history` audit trail table: `id` (UUID), `retailer_id` (FK `retailers.id`), `admin_id` (FK `users.id`), `action` (VARCHAR 64), `from_status` (VARCHAR 32), `to_status` (VARCHAR 32), `reason` (Text), `created_at`.
  - Added deal scope, targeting, and usage columns to `discounts`: `scope` (VARCHAR 32, default `'PLATFORM_WIDE'`), `category_id` (FK `categories.id`), `product_id` (FK `products.id`), `usage_limit` (Integer), `times_used` (Integer, default 0), `description` (Text). Reversible upgrade and downgrade cleanly verified.
- **Canonical Catalogue Management:**
  - Mounted `GET /api/v1/admin/catalogue/products`, `POST /api/v1/admin/catalogue/products`, `GET /api/v1/admin/catalogue/products/{id}`, `PUT /api/v1/admin/catalogue/products/{id}`, and `DELETE /api/v1/admin/catalogue/products/{id}`.
  - Mounted variant endpoints: `POST /api/v1/admin/catalogue/products/{id}/variants`, `PUT /api/v1/admin/catalogue/variants/{id}`, and `DELETE /api/v1/admin/catalogue/variants/{id}`.
  - Mounted category endpoints: `GET /api/v1/admin/catalogue/categories` and `POST /api/v1/admin/catalogue/categories`.
  - **Canonical Specifications Invariant:** Admin editing canonical master products, attributes, or variants updates the catalogue blueprint and duplicate SKU/slugs are rejected; canonical edits strictly never alter existing retailer listings, independent selling prices, or retailer stock levels.
- **Retailer Verification & Compliance Desk:**
  - Mounted `GET /api/v1/admin/retailers/{id}` returning store details, submitted compliance documents, and full verification history audit trail.
  - Mounted `POST /api/v1/admin/retailers/{id}/verify` and `POST /api/v1/admin/retailers/{id}/documents/{doc_id}/verify`, persisting reviewer `admin_id`, timestamp, decision, and audit reason.
  - **Verification Status Enforcement:** `RetailerService` strictly enforces verification status on all operational endpoints. Unverified (`PENDING`), `REJECTED`, or `SUSPENDED` retailers are blocked with HTTP 403 (`RETAILER_NOT_VERIFIED` or `RETAILER_SUSPENDED`) from creating listings, updating listings, deleting listings, or adjusting warehouse inventory.
- **Platform Deals & Dynamic Promotion Engine:**
  - Mounted `GET /api/v1/admin/deals`, `POST /api/v1/admin/deals`, `GET /api/v1/admin/deals/{id}`, `PUT /api/v1/admin/deals/{id}`, and `DELETE /api/v1/admin/deals/{id}` guarded by `require_admin`.
  - Supports scopes (`PLATFORM_WIDE`, `CATEGORY`, `PRODUCT`, `LISTING`), discount types (`PERCENTAGE` up to 90%, `FIXED_AMOUNT`), min order thresholds, max discount caps, usage limits, and scheduling (`valid_from`, `valid_to`).
  - **Pricing Integrity Invariant:** Platform promotions dynamically calculate in `DiscountService` during cart and checkout quote generation without overwriting retailer-specific base prices or retailer inventory.
- **Frontend Admin Consoles:**
  - `/admin/layout.tsx`: Refined operations desk navigation highlighting active route tabs and public/retailer cross-links.
  - `/admin/page.tsx`: Added quick-access module cards directly launching Retailers & Verification, Platform Catalogue, and Deals & Promotions.
  - `/admin/retailers/page.tsx`: Status-filtered retailer directory, real-time search, inspection drawer with submitted documents, verification controls, and decision modal with required audit reason notes.
  - `/admin/catalogue/page.tsx`: Platform catalogue manager with search, category filtering, product creation/edit modals, and variant SKU manager.
  - `/admin/deals/page.tsx`: Promotional deals dashboard with status filtering (Active, Scheduled, Paused, Expired), deal cards, active toggle, and deal creation/edit modal.

### 4.6 Phase 5C.1 Marketplace Authenticity, Customer Product Visibility, Inventory Synchronization & Retailer Sales Analytics
- **Authentic Retailers & Seeding:** Seeded 15 authentic, geographically diverse Indian verified retailers (Bengaluru KA, Mumbai MH, Delhi DL, Hyderabad TS, Chennai TN, Pune MH, Ahmedabad GJ, Kolkata WB, Jaipur RJ, Kochi KL, Chandigarh CH, Noida UP, Gurugram HR, Indore MP, Lucknow UP) with realistic GSTINs and physical addresses. Soft-deactivated legacy artificial dummy retailers while safeguarding foreign-key integrity. Seeded 10 core commercial categories and 77 canonical products with realistic INR market pricing. OpenSearch indexes and write/read aliases synchronized.
- **Customer Storefront Multi-Seller Offers & Visibility:**
  - Enforced server-side filtering across catalogue repository, search documents, and product detail queries to strictly exclude unverified, inactive, or suspended retailers from customer view.
  - Added `retailer_state` to `ProductListingDetailSchema` to power regional seller badges.
  - On the Product Detail Page (`/products/[id]`), implemented interactive Multi-Seller Offer comparison cards with store name, customer rating, merchant state, stock status, MRP, selling price, and discount percentage, allowing shoppers to choose which retailer's offer to add to cart.
  - Displays a clean "Currently Unavailable" state when no active, verified retailers offer the item.
- **Atomic Inventory Deduction & Idempotency:**
  - 10-minute hold on `reserved_quantity` upon checkout reservation creation.
  - Atomic permanent deduction (`on_hand_quantity -= qty`, `reserved_quantity -= qty`) upon payment confirmation (`confirm_reservation`).
  - Idempotent confirmation prevents double-deductions upon duplicate webhook or callback replays.
  - Releasing expired or cancelled reservations restores `reserved_quantity` to 0 without mutating `on_hand_quantity`.
- **Admin Retailer Management & Store-Wise Sales Analytics:**
  - Extended `GET /api/v1/admin/retailers` with multi-field search and registered state filtering (`state=KA`).
  - Mounted `GET /api/v1/admin/retailers/{retailer_id}/analytics` guarded by `require_admin` calculating total orders, units sold, gross merchandise value (GMV), customer refunds, net sales, and per-variant sales breakdowns.
  - Implemented `/admin/retailers/[id]` sales analytics dashboard with 4 KPI cards, store metadata, and product-level sales breakdown table.
- **Verification Evidence:**
  - Added 6 automated integration tests in `backend/tests/test_marketplace_authenticity_and_inventory.py`.
  - Full backend test suite: 390 passed (100%).
  - Full frontend test suite: 68 passed (100%).
  - Full TypeScript type-check and Next.js production build: 0 errors (22/22 pages compiled).

---

## 5. Feature Specification vs. Implementation Matrix

The table below reconciles the finalized feature specification (`FEATURE_SPECIFICATION.md`) against current implementation status (`IMPLEMENTATION_STATUS.md`):

| Feature Area | Role | Finalized Spec Status | Codebase Implementation Status | Current Notes & Evidence |
|:---|:---:|:---:|:---:|:---|
| **Product Catalogue & Variants** | Admin / Retailer / Customer | Core | **Fully Implemented** | Database models, API routes, SSR storefront browsing. |
| **Retailer Catalogue Listings (2.2)** | Retailer | Core | **Fully Implemented (Phase 5B)** | Listing creation from platform catalogue, custom seller SKUs, active/paused toggles, deduplication. |
| **Retailer Variant Pricing (2.3)** | Retailer | Core | **Fully Implemented (Phase 5B)** | Independent selling price & MRP per variant, margin validation, no platform catalogue mutation. |
| **Retailer Inventory & Stock (2.6)** | Retailer | Core | **Fully Implemented (Phase 5B)** | Warehouse console, SET/DELTA adjustments, row locks, hold protection, low-stock threshold alerts. |
| **Faceted Search (OpenSearch)** | Customer | Core | **Fully Implemented** | OpenSearch indexing, facets, circuit breaker, SQL fallback. |
| **Persistent Cart & Merging** | Customer | Core | **Fully Implemented** | Guest carts, authenticated carts, automated merge on login. |
| **Pricing & HMAC Quotes** | Platform / Retailer | Core | **Fully Implemented** | GST tax computation, discounts, 5-minute signed quotes. |
| **Inventory Reservations** | System | Core | **Fully Implemented** | All-or-nothing stock locking, row locks, 10-minute expiry. |
| **Checkout & Order Creation** | Customer | Core | **Fully Implemented** | Atomic PostgreSQL orders, immutable item snapshots, outbox, server-authoritative reservation derivation. |
| **Razorpay Payment Gateway** | Platform / Customer | Core | **Fully Implemented** | Dual-mode sandbox, server capture verification, HMAC webhooks. |
| **Transactional Outbox & Kafka** | System | Core | **Fully Implemented** | Outbox publisher, lease fencing, Kafka SASL_SSL, consumer inbox. |
| **Order Tracking (7 Stages)** | Customer | Core | **Fully Implemented** | 7-stage visual tracker, carrier consignments, external URLs. |
| **Order Cancellations & Returns** | Customer | Core | **Fully Implemented** | Pre-dispatch cancellation, post-delivery returns & inspections. |
| **Customer Notifications** | Customer | Core | **Fully Implemented** | In-app notification center, unread counters, mark as read. |
| **Customer Account Management** | Customer | Core | **Fully Implemented** | Profile, saved addresses, recent purchases, session revoke. |
| **Admin Panel Dashboard** | Admin | Core | **Fully Implemented (Phase 5C)** | Overview KPIs, retailer compliance verification, canonical catalogue manager, promotional deals engine, `/admin/*`. |
| **Retailer Panel Dashboard** | Retailer | Core | **Expanded (Phase 5A + 5B)** | Store profile, open/pause toggle, `/retailer/listings`, `/retailer/inventory`, overview metrics. |
| **Role-Based Access Control (RBAC)** | Platform | Core | **Fully Implemented (Phase 5A)** | `users.role`, server-side `require_admin`, `require_retailer`, tenant isolation `get_current_retailer`. |
| **Basket Mission & Intent Memory** | Customer | Core Differentiator | **Planned (Phase 6)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.2, §3.3. |
| **Substitute & Price Intelligence** | Customer | Core Differentiator | **Planned (Phase 6)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.4, §3.10. |
| **Demand Gap & Community Buying** | Admin / Retailer / Customer | Core Differentiator | **Planned (Phase 6)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.5, §3.6, §3.7. |
| **AI Negotiator & Dukaan vs Dukaan**| Retailer / Customer | Core Differentiator | **Planned (Phase 7)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.8, §3.9. |
| **Basket Product Passport** | Customer | Core Differentiator | **Planned (Phase 7)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.11. |
| **Bharat Multilingual** | Customer | Core Differentiator | **Planned (Phase 7)** | Spec defined in `FEATURE_SPECIFICATION.md` §3.13. |
| **Handwritten List to Basket** | Customer | Optional | **Planned (Phase 7)** | Optional auxiliary feature; spec defined in §3.14. |
| **Sale Stream Rewind** | Customer | Removed | **Removed** | Formally removed from product specification. |
