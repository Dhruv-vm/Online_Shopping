# BASKET — Shared Agent Handoff & Conversation Log

> This is the coordination document between Developer A, Developer B, and their Antigravity agents. It is not a place for vague status updates. Record decisions, requests, blockers, and integration notes so the other developer can continue without guessing.

## 1. Rules for using this file

- Append a new entry; do not silently rewrite or delete another person's entry.
- Use timestamps in IST (`YYYY-MM-DD HH:MM IST`).
- Identify the author: `Developer A`, `Developer B`, or `Integration Owner`.
- Every request must state what response/action is needed and by when.
- Every shared API/schema change must be written here before implementation.
- The receiving developer must reply in a new entry with `ACCEPTED`, `REJECTED`, or `NEEDS DISCUSSION`.
- A handoff is not approval to merge. GitHub PR review is still required.
- Keep entries concise, factual, and actionable.
- Do not paste secrets, tokens, private customer data, or huge logs. Link to a sanitized log or PR instead.

## 2. Current team ownership

| Area | Owner | Backup/reviewer |
|---|---|---|
| Integration branch and shared contracts | To be assigned | Other developer |
| Frontend foundation | Developer A/B — decide together | Other developer |
| Backend foundation and DB migrations | Developer A/B — decide together | Other developer |
| Catalogue/search | To be assigned | To be assigned |
| Cart/checkout/orders | To be assigned | To be assigned |
| Kafka/outbox/workers | To be assigned | To be assigned |
| Optional differentiators | To be assigned | To be assigned |

Fill this table before parallel implementation.

## 3. Current shared baseline

- Base branch: `integration` (create if it does not exist).
- Stable branch: `main`.
- Stack: Next.js + TypeScript; FastAPI + SQLAlchemy 2 + Alembic; Aiven PostgreSQL, Kafka, OpenSearch.
- API prefix: `/api/v1`.
- Database authority: PostgreSQL.
- Search authority: OpenSearch only for retrieval, never checkout validation.
- Event publication: transactional outbox.
- Payment: Razorpay Sandbox only when configured and server-verified.

## 4. Entry template — proposal/request

Copy this section for every new request.

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [PROPOSAL / REQUEST / BLOCKER]

**Related branch / PR / task:**
**Affected module(s):**
**What I am proposing or requesting:**
**Reason:**
**Files/contracts affected:**
**Backward compatibility impact:**
**What I need from the other developer:**
**Required response by:**

**Status:** OPEN

---

## 5. Entry template — response

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [RESPONSE]

**Replying to:**
**Decision:** ACCEPTED / REJECTED / NEEDS DISCUSSION
**Reason:**
**Required follow-up:**
**Owner:**
**Status:** OPEN / RESOLVED

---

## 6. Entry template — implementation handoff

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [IMPLEMENTATION HANDOFF]

**Task:**
**Branch / PR:**
**What is implemented:**
**Files changed:**
**API/schema/event changes:**
**Migration details:**
**Tests and results:**
**Known limitations:**
**How to run or verify:**
**What the next developer should do:**

**Status:** READY FOR REVIEW / BLOCKED / NEEDS FOLLOW-UP

---

## 7. Integration incident template

### [YYYY-MM-DD HH:MM IST] — [AUTHOR] — [INTEGRATION INCIDENT]

**Observed failure:**
**Steps to reproduce:**
**Expected behaviour:**
**Actual behaviour:**
**Relevant branch/commit/PR:**
**Logs (sanitized):**
**Suspected owner/module:**
**Immediate containment:**
**Resolution:**

**Status:** OPEN / RESOLVED

---

## 8. Live log

### [2026-11-16 17:40 IST] — Foundation Engineer — [IMPLEMENTATION HANDOFF]

**Task:** Phase 0 — Monorepo Foundation and Quality Gate Baseline
**Branch / PR:** `feature/phase0-foundation` -> `integration`
**What is implemented:**
1. Git repository initialized with `main` and `integration` remote branches; comprehensive `.gitignore` configured to prevent secret or artifact leakage.
2. Backend modular monolith setup:
   - Python 3.12 managed via `uv`.
   - FastAPI application factory in `backend/app/main.py`.
   - Pydantic Settings with startup validation and SecretStr credential masking (`backend/app/core/config.py`).
   - Structured logging (`backend/app/core/logging.py`).
   - Centralized exception handlers adhering to `API_CONTRACTS.md` standard error format (`backend/app/core/exceptions.py`).
   - SQLAlchemy 2.x async engine with Aiven PostgreSQL SSL support and session lifecycle (`backend/app/core/database.py`).
   - Single-head Alembic baseline migration harness (`backend/alembic/versions/0001_initial_baseline.py`).
   - Process liveness (`/health`) and database readiness (`/ready`) endpoints.
   - Pytest unit tests (6/6 passing) and Ruff lint/format checks configured and passing.
3. Frontend Next.js 15 baseline:
   - Next.js 15 App Router with React 19 and strict TypeScript (`frontend/tsconfig.json`).
   - Tailwind CSS and shadcn/ui component primitives (`Button`, `Card`, `Badge`).
   - Centralized, strongly-typed API client with `ApiClientError` and environment-based base URL (`frontend/lib/api/client.ts`).
   - Live system status monitoring component displaying backend health and database readiness (`frontend/components/shared/system-status.tsx`).
   - Foundation landing page and responsive layout (`frontend/app/page.tsx`, `frontend/app/layout.tsx`).
4. Infrastructure and Developer Tooling:
   - Zero-secret environment templates (`backend/.env.example`, `frontend/.env.example`, `infra/.env.example`).
   - Bootstrap script (`scripts/dev-setup.sh`) and verification gate script (`scripts/verify-environment.sh`).
   - Updated control center documentation (`README.md`).

**Files changed:**
- Created: `backend/**`, `frontend/**`, `infra/**`, `scripts/**`, `.gitignore`.
- Updated: `README.md`, `AGENT_HANDOFF.md`.
- Preserved untouched: `PROJECT_CHARTER.md`, `ARCHITECTURE.md`, `AGENT_RULES.md`, `API_CONTRACTS.md`, `DATA_MODEL.md`, `DEVELOPMENT_WORKFLOW.md`, `TASK_BREAKDOWN.md`, `QUALITY_GATES.md`, `DECISIONS.md`.

**API/schema/event changes:**
- Endpoints added: `GET /health`, `GET /ready`, `GET /api/v1/info`.
- Standard error envelope conforming to `API_CONTRACTS.md`.

**Migration details:**
- Alembic single head: `0001_initial_baseline`. Verified upgrade and downgrade compatibility.

**Tests and results:**
- Backend: `pytest -v` (6/6 passed in 0.01s).
- Backend lint & format: `ruff check .` (0 errors), `ruff format --check .` (clean).
- Frontend: TypeScript check and build verification pending npm install task completion.

**Known limitations:**
- Direct PostgreSQL CLI (`psql`) is not installed on the host machine; database operations in Phase 0 run via Python asyncpg/SQLAlchemy and Alembic drivers.
- External Aiven service credentials (PostgreSQL, Kafka, OpenSearch) and Razorpay keys are not yet configured in local `.env` files; `/ready` reports database status as `"unconfigured"` by design until credentials are provided.

**How to run or verify:**
- Run `./scripts/verify-environment.sh` from the repository root.
- Run `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`.
- Run `cd frontend && npm run dev`.

**What the next developer should do:**
1. Review and approve `feature/phase0-foundation` PR.
2. Fill developer role assignments in `TASK_BREAKDOWN.md` for Phase 1 parallel work.

**Status:** READY FOR REVIEW

---

### [2026-11-16 19:35 IST] — Lead Full-Stack Engineer — [IMPLEMENTATION HANDOFF]

**Task:** Phase 1 — Catalogue & Storefront Foundation
**Branch / PR:** `feature/phase1-catalogue-storefront`
**What is implemented:**
1. **Backend Catalogue Domain Models (`backend/app/modules/catalogue/models.py`):**
   - `Retailer`: UUID pk, name, unique slug, logo_url, rating, is_active, timestamps.
   - `Category`: UUID pk, name, unique slug, description, image_url, icon, self-referential parent_id, timestamps.
   - `Product`: UUID pk, category_id FK, name, unique slug, brand, description, is_active, timestamps.
   - `ProductVariant`: UUID pk, product_id FK, name, unique sku, attributes JSONB, is_active, timestamps.
   - `ProductImage`: UUID pk, product_id FK, variant_id FK, url, alt_text, is_primary, sort_order.
   - `ProductListing`: UUID pk, retailer_id FK, variant_id FK, seller_sku, original_price_paise, selling_price_paise, currency (INR), is_active. Check constraints enforcing non-negative prices and unique constraint on `(retailer_id, variant_id)`.
   - `StoreInventory`: UUID pk, listing_id FK (unique), on_hand_quantity, reserved_quantity. Check constraints enforcing non-negative quantities and `on_hand >= reserved`.
2. **Alembic Migration (`backend/alembic/versions/0002_catalogue_schema_create_catalogue_tables.py`):**
   - Clean single head `0002_catalogue_schema` building on `0001_initial_baseline`.
   - Verified reversible migration with automated `upgrade head` and `downgrade -1`.
3. **Repository & Service Layers (`backend/app/modules/catalogue/`):**
   - `CatalogueRepository`: Async SQLAlchemy 2.0 queries, eager relation loading with `selectinload()`, dynamic multi-parameter filtering, and multi-criteria sorting.
   - `CatalogueService`: Aggregate price/stock computations, variant option mapping, error envelopes with `AppException`.
4. **Catalogue API Endpoints (`backend/app/modules/catalogue/router.py` mounted at `/api/v1`):**
   - `GET /api/v1/categories`: Lists categories with active product counts.
   - `GET /api/v1/retailers`: Lists active retailers with ratings.
   - `GET /api/v1/products`: Filterable catalogue with pagination, search, category, retailer, brand, price range, and in-stock toggles.
   - `GET /api/v1/products/{id}`: Detailed product view with full variants, images, competing retailer listings, and real-time inventory.
5. **Seed Data (`backend/app/seeds/seed_catalogue.py`):**
   - Comprehensive, idempotent seed script covering all 7 requested Indian retail categories: Electronics, Fashion, Groceries, Beauty & Wellness, Home & Furniture, Sports & Fitness, Books & Stationery.
   - Seeds 7 major retailers (Reliance Digital, Croma, Tata CLiQ, Nature's Basket, FabIndia, Decathlon India, Crossword Bookstore), products with multiple variants, images, and live inventory.
6. **Frontend Storefront UI (`frontend/`):**
   - Universal Homepage (`frontend/app/page.tsx`): Hero showcase, category department tiles, live featured products, retailer showcase, platform architecture guarantees, live system status.
   - Catalogue Listing Page (`frontend/app/products/page.tsx`): Full interactive catalogue browsing with live filters (categories, retailers, price range, in-stock only), sorting selector, search query response, pagination controls, and mobile filter sheet.
   - Product Detail Page (`frontend/app/products/[id]/page.tsx`): Image gallery with thumbnail switcher, category breadcrumb, variant selection, competing retailer offer comparison cards with best offer badge, real-time stock indicator, and specifications.
   - Categories Directory (`frontend/app/categories/page.tsx`) & Retailers Directory (`frontend/app/retailers/page.tsx`).
   - Responsive Header (`frontend/components/shared/header.tsx`): Live search form with URL navigation, mobile drawer menu, and category navigation.
   - Typed API Client (`frontend/lib/api/client.ts`): Expanded with strongly typed methods (`getCategories`, `getRetailers`, `getProducts`, `getProduct`) and test coverage.
7. **Verification & Quality Gates:**
   - Backend: 24/24 unit & integration tests passing (`pytest -v`), Ruff lint & format clean (0 errors).
   - Frontend: 10/10 tests passing (`npm test`), TypeScript check clean (`npm run type-check`), production build clean (`next build`).
   - Unified Gate: `./scripts/verify-environment.sh` exits 0 with all checks passing.

**Files changed:**
- Created:
  - `backend/app/modules/catalogue/__init__.py`
  - `backend/app/modules/catalogue/models.py`
  - `backend/app/modules/catalogue/schemas.py`
  - `backend/app/modules/catalogue/repository.py`
  - `backend/app/modules/catalogue/service.py`
  - `backend/app/modules/catalogue/router.py`
  - `backend/app/seeds/__init__.py`
  - `backend/app/seeds/seed_catalogue.py`
  - `backend/alembic/versions/0002_catalogue_schema_create_catalogue_tables.py`
  - `backend/tests/test_catalogue.py`
  - `frontend/components/catalogue/product-card.tsx`
  - `frontend/components/catalogue/category-card.tsx`
  - `frontend/components/catalogue/product-filters.tsx`
  - `frontend/components/ui/input.tsx`
  - `frontend/app/products/page.tsx`
  - `frontend/app/products/[id]/page.tsx`
  - `frontend/app/categories/page.tsx`
  - `frontend/app/retailers/page.tsx`
- Modified:
  - `backend/app/api/v1/router.py` (mounted catalogue router)
  - `backend/app/core/config.py` (env_file multi-path discovery)
  - `backend/alembic.ini` (standardized version location)
  - `backend/alembic/env.py` (discovered catalogue models)
  - `backend/tests/conftest.py` (scoped async engine cleanup per test loop)
  - `frontend/types/index.ts` (catalogue types and filter params)
  - `frontend/lib/api/client.ts` (typed catalogue API methods)
  - `frontend/lib/api/client.test.ts` (catalogue unit test assertions)
  - `frontend/components/shared/header.tsx` (live search & navigation)
  - `frontend/components/shared/footer.tsx` (links & Phase 1 footer)
  - `frontend/app/page.tsx` (connected live storefront homepage)
  - `scripts/verify-environment.sh` (backend directory test runner consistency)
  - `TASK_BREAKDOWN.md` (checked Phase 0 & Phase 1 deliverables)

**API/schema/event changes:**
- `GET /api/v1/categories`
- `GET /api/v1/retailers`
- `GET /api/v1/products`
- `GET /api/v1/products/{id}`

**Migration details:**
- Head revision: `0002_catalogue_schema` (down revision: `0001_initial_baseline`).

**Tests and results:**
- Backend: `pytest -v` (24 passed in 0.54s).
- Backend lint & format: `ruff check .` (0 errors), `ruff format --check .` (clean).
- Frontend unit tests: `npm test` (10 passed in 170ms).
- Frontend type check: `npm run type-check` (clean).
- Frontend production build: `npm run build` (compiled successfully, 6 routes generated).
- Master gate: `./scripts/verify-environment.sh` (ALL VERIFICATION GATES PASSED CLEANLY).

**Known limitations:**
- Full-text search currently executes authoritative SQL ILIKE queries over names, brands, descriptions, and category names in PostgreSQL; Aiven OpenSearch indexing and query delegation is scheduled for Phase 2/3.
- Cart state persistence, inventory reservation state machine, and payment gateways will be implemented in Phase 2 per project charter.

**How to run or verify:**
- Master quality gate: `bash scripts/verify-environment.sh`
- Start backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000`
- Start frontend: `cd frontend && npm run dev`

### [2026-11-16 21:30 IST] — Lead Full-Stack Engineer — Phase 1 Final Polish Resolved

**Related branch / PR / task:** `feature/phase1-catalogue-storefront` — Post-Audit Polish (M-1, L-1, L-2)
**Affected module(s):** Storefront UI, Seed Data

**Work completed:**
1. **M-1 Category Card Truncation**: Removed hard `truncate` constraint from `category-card.tsx`; enabled `line-clamp-2` with `min-w-0 flex-1` and responsive grid on desktop (`xl:grid-cols-7`, `lg:grid-cols-4`, `md:grid-cols-3`, `grid-cols-2`). All 7 department titles (including "Beauty & Wellness" and "Books & Stationery") wrap cleanly with zero ellipsis cutoff.
2. **L-1 Seed Image Corrections**: Replaced broken and mismatched URLs in `backend/app/seeds/seed_catalogue.py` with verified, matching photos for Chelsea boots, Kashmir acacia honey, Kumkumadi night cream, Featherlite executive chair, and Lamy 2000 fountain pen. Updated database rows idempotently via seed update logic.
3. **L-2 Hero CTA Contrast**: Replaced low-contrast translucent outline button with high-contrast styling (`bg-white/10 border-2 border-emerald-300/40 text-white font-semibold hover:bg-white/20`) on both desktop and mobile viewports.

**Verification & Quality Gates:**
- Pytest: 24/24 passing in 0.48s.
- Ruff: 0 errors, 23 files formatted clean.
- Frontend Tests: 10/10 passing in 196ms.
- Frontend TypeScript & Build: `tsc --noEmit` clean, `next build` clean (all 6 routes).
- Full Environment Verification: `bash scripts/verify-environment.sh` exits 0 with `ALL VERIFICATION GATES PASSED CLEANLY`.
- Headless Browser Verification: Verified at 1280x900 and 375x812 with full screenshot inspection.

**Status:** COMPLETE (Merged into integration)

---

### [2026-11-16 21:55 IST] — Lead Full-Stack Engineer — Phase 2 Architecture Finalized

**Related branch / PR / task:** Phase 2 Architecture Design (`PHASE_2_ARCHITECTURE.md`)
**Affected module(s):** Commerce Engine, Identity, Cart, Quotes, Inventory, Orders, Payments, Outbox

**Work completed:**
1. Produced and finalized the complete Phase 2 architecture design incorporating all mandatory corrections in `PHASE_2_ARCHITECTURE.md`.
2. Verified exact foreign key alignment against Phase 1 tables (`retailers`, `categories`, `products`, `product_variants`, `product_listings`, `store_inventory`).
3. Specified listing-level HSN tax brackets (0%, 5%, 12%, 18%, 28%) and intra-state CGST/SGST vs inter-state IGST calculation.
4. Defined decoupled Razorpay gateway boundaries (external HTTP calls outside PostgreSQL transactions), multi-factor server payment verification, raw-body webhook HMAC verification, and `REQUIRES_RECONCILIATION` state for gateway timeouts.
5. Specified deterministic lock ordering by `listing_id` and conditional state transitions for reservation expiry vs payment races.
6. Specified complete authentication lifecycle (Argon2id, JWT cookie security, refresh token rotation with family reuse detection, session invalidation, login rate limiting, and email normalization).
7. Clarified delivery thresholds (₹0 for $\ge$ ₹499; ₹49 for $<$ ₹499 per retailer) and at-most-one default address partial index constraint.
8. Established Phase 2 / Phase 3 boundary: PostgreSQL `outbox_events` implemented in Phase 2; Kafka publisher/consumers deferred to Phase 3.

**Implementation Sequence Approved:**
- 2A Identity and Addresses
- 2B Persistent Cart
- 2C Pricing and Quotes
- 2D Inventory Reservations
- 2E Orders and Checkout
- 2F Razorpay Payments and Recovery
- 2G Frontend Integration and End-to-End Testing

**Status:** APPROVED FOR IMPLEMENTATION

---

### [2026-11-16 22:45 IST] — Lead Full-Stack Engineer — Phase 2A Identity & Authentication Implemented

**Related branch / PR / task:** `feature/phase2-identity-addresses` — Slice 2A Backend Foundation
**Affected module(s):** `backend/app/modules/identity/`, Alembic migrations, Auth APIs

**Work completed:**
1. **Database Models (`backend/app/modules/identity/models.py`):**
   - `User`: Normalized unique email, phone, full name, Argon2id hashed password, role (`customer`), active flag, and timestamps.
   - `UserSession`: Refresh token hash (SHA-256), `family_id` (UUID), `is_revoked`, user agent, IP address, and expiry.
   - `Address`: Recipient name, phone, line1, line2, city, state, 6-digit postal code check constraint, and partial unique index `uq_user_default_address` guaranteeing at most one default address per customer.
2. **Alembic Migration (`backend/alembic/versions/0003_identity_schema_create_users_sessions_addresses.py`):**
   - Single clean head: `0003_identity_schema` building on `0002_catalogue_schema`.
   - Verified bidirectional execution: `alembic upgrade head` and `alembic downgrade -1` both pass with zero schema corruption.
3. **Security & Authentication Engine (`backend/app/modules/identity/security.py`):**
   - Password hashing: Argon2id (`time_cost=3`, `memory_cost=64MB`, `parallelism=4`).
   - JWT tokens: HS256 with 256-bit secret, 15-minute access token lifespan, explicit `token_use` claim.
   - Refresh token lifecycle: High-entropy tokens, SHA-256 storage, single-use rotation, and family-wide revocation upon reuse detection.
   - Session invalidation: Specific session revocation on logout, all-session revocation on logout-all.
   - Rate limiting: Sliding-window limiter enforcing 5 attempts / 60 seconds and 15-minute lockout on 10 failures.
   - CSRF protection: Double-submit `XSRF-TOKEN` cookie validated against `X-CSRF-Token` header.
   - Secure cookies: HTTP-only, SameSite configured, Path-scoped cookies.
4. **FastAPI Endpoints (`backend/app/modules/identity/router.py` mounted at `/api/v1`):**
   - `POST /api/v1/auth/register` (201 Created)
   - `POST /api/v1/auth/login` (200 OK)
   - `POST /api/v1/auth/refresh` (200 OK)
   - `POST /api/v1/auth/logout` (200 OK)
   - `POST /api/v1/auth/logout-all` (200 OK)
   - `GET /api/v1/users/me` (200 OK)
5. **Quality Gates & Tests (`backend/tests/test_identity.py`):**
   - 16 new automated tests covering registration, duplicate emails, password validation, Argon2id verification, JWT expiration, refresh rotation, replay attack detection, logout invalidation, logout-all, CSRF enforcement, rate limiting, and RBAC isolation.
   - Total backend test suite: 40/40 passing in 1.66s.
   - Ruff lint & format: 0 errors across all 33 backend files.
   - Unified verification gate: `scripts/verify-environment.sh` passes cleanly.

**Remaining in Phase 2A:** Customer address CRUD endpoints and Address Management UI.
**Next slice in pipeline:** Customer address endpoints, followed by Slice 2B: Persistent Cart Domain.

**Status:** COMPLETE (Checkpoint 1 — Identity Backend Foundation)

---

### [2026-11-16 23:05 IST] — Lead Full-Stack Engineer — Phase 2A Security Audit & Address Management Backend Complete

**Related branch / PR / task:** `feature/phase2-identity-addresses` — Checkpoint 2 (Security Hardening & Address CRUD)
**Affected module(s):** `backend/app/modules/identity/`, `backend/app/api/v1/router.py`, `backend/tests/test_identity.py`

**Work completed:**
1. **Authentication Security Audit & Hardening:**
   - **Refresh token concurrency:** Implemented pessimistic row-locking (`for_update=True` via `stmt.with_for_update()`) on `get_session_by_token_hash`. Concurrent refresh requests serialize at the database level, preventing replay race conditions.
   - **Access-token revocation:** Added session UUID (`sid`) to JWT payload. `get_current_user` dependency performs instantaneous revocation check by validating `user_sessions.is_revoked is False`, ensuring immediate access invalidation on logout and logout-all.
   - **CSRF & Cookie Security:** Added `Origin` / `Referer` header validation against `settings.CORS_ORIGINS` for cookie-based state-mutating requests. Hardened `verify_csrf_token` to bypass CSRF checks only when explicit `Authorization: Bearer` headers are present. Validated `HttpOnly`, `SameSite=Lax/Strict`, and path scoping (`/api/v1/auth`).
   - **Role escalation protection:** Fixed registration service to enforce hardcoded `customer` role, rejecting any privilege escalation attempt.
   - **Deactivated account blocking:** Inactive accounts (`is_active=False`) are blocked at login (401), session access (403), and refresh (403 with session revocation).
2. **Customer Address Management:**
   - Implemented address CRUD services in `IdentityService` and repository queries in `IdentityRepository`.
   - **Single default address constraint:** Enforced at DB engine level via partial unique index `uq_user_default_address`. Handled via atomic transactions with `clear_default_addresses`.
   - **Zero-address & first-address rules:** New accounts start with 0 addresses. The first created address automatically becomes `is_default=True`.
   - **Promotion on deletion:** Deleting the active default address automatically promotes the oldest remaining address (`ORDER BY created_at ASC LIMIT 1`) to default. Deleting the last remaining address cleanly returns the user to 0 addresses.
   - **Customer data isolation:** Multi-tenant address queries enforce `user_id = current_user.id`, returning 404 on any unauthorized address access or mutation attempt.
   - **Indian postal code validation:** Enforced via Pydantic validator and DB check constraint `chk_indian_postal_code` (`^[1-9][0-9]{5}$`).
3. **Endpoints Mounted under `/api/v1/addresses`:**
   - `GET /api/v1/addresses` (200 OK — list user addresses, default first)
   - `POST /api/v1/addresses` (201 Created — create address, CSRF protected)
   - `PATCH /api/v1/addresses/{id}` (200 OK — update address, CSRF protected)
   - `DELETE /api/v1/addresses/{id}` (200 OK — delete address, CSRF protected)
4. **Verification Gates & Test Suite:**
   - Added 9 new rigorous test cases to `backend/tests/test_identity.py` (total 25 identity tests).
   - Entire backend pytest suite: **49/49 tests passing** in 2.56s.
   - Ruff lint & format: **0 errors** across all 33 backend files.
   - Full environment verification script (`scripts/verify-environment.sh`): **ALL GATES PASSED CLEANLY** (backend tests, Alembic discovery, TypeScript typecheck, Next.js production build).

**Status:** COMPLETE (Checkpoint 2 — Identity Security Hardening & Address Management Backend)

---

### [2026-11-16 23:40 IST] — Lead Full-Stack Engineer — Phase 2A Customer Authentication & Address Experience Complete

**Related branch / PR / task:** `feature/phase2-identity-addresses` — Phase 2A Frontend Implementation & End-to-End Verification
**Affected module(s):** `frontend/app/`, `frontend/components/`, `frontend/lib/`, `frontend/types/`

**Work completed:**
1. **API Client & Authentication Infrastructure (`frontend/lib/api/client.ts`):**
   - Configured `credentials: "include"` by default on all requests. All auth tokens live exclusively in secure HTTP-only cookies; zero tokens stored in `localStorage` or `sessionStorage`.
   - Built automatic CSRF header injection: reads `XSRF-TOKEN` cookie in the browser and attaches `X-CSRF-Token` header on all state-mutating requests (`POST`, `PATCH`, `PUT`, `DELETE`).
   - Implemented single-flight concurrency-safe token refresh: if an authenticated request returns 401, a shared `executeTokenRefresh` promise resolves `/api/v1/auth/refresh` once for all concurrent callers, retrying original requests without duplicate refresh calls.
   - Added strongly-typed client methods: `register`, `login`, `refreshToken`, `logout`, `logoutAll`, `getProfile`, `getAddresses`, `createAddress`, `updateAddress`, `deleteAddress`.
2. **Global Auth State & Route Protection:**
   - `AuthProvider` (`frontend/lib/auth/auth-context.tsx`): Manages `user`, `isLoading`, and `isAuthenticated` lifecycle, automatically hydrating profile on mount.
   - `<ProtectedRoute>` (`frontend/components/auth/protected-route.tsx`): Guards private account routes with animated loading skeleton; redirects unauthenticated visitors to `/login?redirect=...`.
3. **Polished Storefront Pages & Components:**
   - **Customer Registration (`/register`):** Full name, email, phone, password, and confirm password fields with client validation, password strength requirements, and 409 conflict handling.
   - **Customer Sign In (`/login`):** Email and password inputs with password visibility toggle, 401 invalid credentials handling, and 429 rate limit cooldown messaging.
   - **Customer Account Overview (`/account`):** Customer greeting banner, verified profile details, member-since timestamp, and security overview with "Sign out from all devices" action.
   - **Address Book (`/account/addresses`):** Full address CRUD experience with "Default Address" badge, Indian states dropdown, 6-digit PIN code validation (`^[1-9][0-9]{5}$`), inline add/edit form, empty state, and delete confirmation.
   - **Responsive Header (`frontend/components/shared/header.tsx`):** Displays dynamic user greeting, Account link, and Sign Out action when authenticated; Sign In and Register CTA buttons when guest.
4. **Automated Testing & Full Verification:**
   - Added 15 new automated frontend tests in `frontend/lib/api/auth-address.test.ts` (total 25 frontend tests across 2 test suites).
   - All 25 frontend tests passing in Node 22+ runner.
   - Frontend TypeScript type check (`tsc --noEmit`): 0 errors.
   - Next.js production build (`next build`): 100% clean compilation across all 9 static and dynamic routes.
   - Backend pytest suite: 51/51 tests passing in 2.45s.
   - Full environment verification script (`scripts/verify-environment.sh`): **ALL GATES PASSED CLEANLY**.

**Status:** COMPLETE (Phase 2A Fully Delivered — Ready for Phase 2B Cart Domain)
