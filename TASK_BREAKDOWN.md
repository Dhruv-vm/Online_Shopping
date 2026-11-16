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
- [ ] **Phase 2B — Persistent Cart Domain & Guest Migration:**
  - [ ] Cart and cart items persistence in PostgreSQL.
  - [ ] Guest session cookie to authenticated user cart consolidation.
  - [ ] Cart endpoints (`GET /api/v1/cart`, `POST /api/v1/cart/items`, `PATCH /api/v1/cart/items/{id}`, `DELETE /api/v1/cart/items/{id}`).
- [ ] **Phase 2C — Pricing, Taxes & Persistent Quotes:**
  - [ ] Listing-level HSN tax brackets (0%, 5%, 12%, 18%, 28%) and CGST/SGST vs IGST engine.
  - [ ] Delivery threshold logic (₹0 for $\ge$ ₹499; ₹49 for $<$ ₹499 per retailer).
  - [ ] Immutable `checkout_quotes` model with 15-minute TTL and single-use consumption.
- [ ] **Phase 2D — Inventory Reservations & Concurrency Protection:**
  - [ ] Lock ordering by `listing_id` to eliminate deadlocks.
  - [ ] Atomic conditional updates and reservation TTL.
  - [ ] High-concurrency oversell tests.
- [ ] **Phase 2E — Orders, Outbox & Checkout Orchestration:**
  - [ ] Immutable order item snapshots and scoped idempotency.
  - [ ] Decoupled checkout transaction boundaries.
  - [ ] Transactional outbox table (`outbox_events`).
- [ ] **Phase 2F — Razorpay Payments, Webhooks & Recovery:**
  - [ ] Decoupled Razorpay order creation.
  - [ ] Multi-factor server-side payment verification and raw-body webhook HMAC check.
  - [ ] `REQUIRES_RECONCILIATION` state and recovery reconciler.
- [ ] **Phase 2G — Storefront UI & End-to-End Verification:**
  - [ ] Cart drawer, full cart page, multi-step checkout stepper, order tracking view.

## 5. Phase 3 — Kafka and reliability

Assign one owner for each task:
- [ ] Transactional outbox schema and service.
- [ ] Outbox publisher to Kafka.
- [ ] Order-created event schema.
- [ ] Idempotent consumer.
- [ ] Consumer reaction (for example, update a read model/index or record a notification job).
- [ ] Retry/error handling and observability.
- [ ] Demonstrate duplicate event does not duplicate side effects.

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
