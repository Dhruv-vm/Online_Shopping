# BASKET — Comprehensive Developer Handoff Guide

> **Target Audience:** Engineering Leads, Full-Stack Developers & System Architects  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Workspace Path:** `/Users/dhruv/dhruv files/basket/Online_Shopping`  
> **Current Feature Branch:** `feature/phase-3-advanced-marketplace` (local; Phase 3 on top of `audit/stabilisation-and-repair` @ `95a5de1`)  
> **Target Base Branch:** `integration`  
> **Handoff Date:** 2026-11-20  

---

## 0. Current handoff — Marketplace Completion (2026-11-21)

Read this section first; the rest of the document describes earlier phases.

### Where things are
- Branch `feature/marketplace-completion` (local only). Base `integration` @ `2610a1e`. Full report: [`docs/MARKETPLACE_COMPLETION.md`](docs/MARKETPLACE_COMPLETION.md). Configuration: [`docs/EXTERNAL_CONFIGURATION.md`](docs/EXTERNAL_CONFIGURATION.md). Open issues: `DISCREPANCY_REGISTER.md` §MC.
- Publishing is handled by Antigravity: **do not push, open PRs, merge or deploy** from a working session. Commit as `Dhruv-vm <vmdhruv1@gmail.com>` with no co-author or session trailers.

### Databases — rules
| Database | Use | Rule |
| --- | --- | --- |
| `basket_db` | Owner's development DB | Never reset. Back up before any change (`scripts/backup-database.sh`). At `0033`; `0034` pending. Test fixtures are hidden by quarantine batch `q-20261120171941`. |
| `basket_demo` | Demo/E2E data | Reset only with `scripts/reset-demo-db.sh` (refuses names not ending `_demo`). |
| `basket_db_test` | pytest | Created/migrated by `tests/conftest.py`; persistent between sessions (see below). |
| `*_verify` | Migration checks | Created and dropped by `scripts/verify-migrations.sh`. |

**Search index:** the repo-root `.env` points OpenSearch at a shared index built from `basket_db`. When you run the API against any other database, start it with `OPENSEARCH_URL=""` (PostgreSQL search) — otherwise search returns another database's products (MC-12).

### Tests — what to know
- Run backend tests with `unset DATABASE_URL` from `backend/`; conftest refuses to use a non-`_test` database. `BASKET_TEST_SKIP_MIGRATE=1` skips the start-of-session migration when the test DB is already at head.
- **The test database is shared and persistent, and fixtures are not cleaned up.** Tests that query the whole catalogue (mission planning, intent personalisation, search) can be affected by rows other tests left behind — especially after *targeted* runs, because full runs later deactivate fixtures via the phase-1 and master-sync seeds. Write new tests against data they create (own category / own retailer), as `test_budget_shortfall_handling` now does. A structural fix (per-test transaction rollback or per-session truncation) is tracked as MC-04.
- `scripts/audit-features.sh` runs the API tests per feature and prints a one-line verdict per area.
- Frontend tests are `node --test` over an explicit file list in `frontend/package.json` — add new test files there.

### i18n — how to extend
- Languages: `frontend/lib/i18n/languages.ts`; dictionaries `frontend/locales/<code>.json`; core key list `frontend/locales/core-keys.json` (every language must translate these — enforced by `lib/i18n/i18n.test.ts`).
- Use `const { t, money, number, date } = useI18n()` in components; `tActive()` outside React; error codes map to `errors.<CODE>`.
- To convert an English page: replace visible strings with `t("area.key")`, add the key to `en.json`, and add translations where available (others fall back to English). Coverage per page is listed in `FRONTEND_BACKEND_STATUS.md`.

### Suggested next work (priority order)
1. Translate the remaining English pages (MC-01): products/search, cart/checkout, orders, account, retailer listings/inventory/orders/offers, admin catalogue/retailers.
2. Configure Razorpay test keys and run a real sandbox payment in the browser (MC-02).
3. Test-database isolation (MC-04).
4. S3-compatible media storage before any multi-instance deployment (MC-06).
5. Public store page (MC-05); OCR adapter against a real provider (MC-08); optional LLM for the assistant (MC-07).

---


## 00. Phase 3 status (2026-11-20)

All nine Phase 3 features are implemented on `feature/phase-3-advanced-marketplace` (local only). Read PHASE_3_FEATURE_TRACKER.md §4, FRONTEND_INTEGRATION_GUIDE.md and TEST_REPORT.md first. Apply migrations to your dev DB with `cd backend && .venv/bin/alembic upgrade head` (dev `basket_db` is still at `0020`). Before go-live: restore the Aiven Kafka service and create topic `basket.events.marketplace`; configure an OCR provider if 3I is wanted; native-speaker review of `frontend/locales/*.json` and `backend/app/modules/i18n/lexicon.py`.

## 0. READ FIRST — Stabilisation Audit Handoff (2026-11-20)

* **Current local branch:** `audit/stabilisation-and-repair` (created from `feature/phase-2d-product-passport` @ `026f801`; safety tag `pre-audit-checkpoint-026f801`). Nothing was pushed, merged or deployed.
* **PR #31:** could not be checked live (no GitHub network access from the audit environment). As of the last local fetch, `origin/integration` is at `9adede6` (PR #30) and does **not** contain `026f801`, so PR #31 appeared unmerged.
* **Corrections to the sections below:**
  * Backend tests run against the PostgreSQL database in `DATABASE_URL` and **mutate inventory rows**. Use a dedicated test DB (see `BACKEND_AUDIT.md` §0.6).
  * Frontend tests use Node's built-in runner (`npm test`), not Vitest.
  * `alembic check` was failing before the audit; `0021` fixes the real gaps; cosmetic drift remains.
  * The search fallback uses escaped `ILIKE`, not `tsvector`.
  * Endpoint count: 148 operations (145 under `/api/v1`).
* **Verified results on this branch:** backend **467 passed / 0 failed / 0 skipped** on PostgreSQL 16, ruff clean, frontend type-check / lint / 100 tests / build all green.
* **Not verified:** live Kafka broker, live OpenSearch cluster, live Razorpay sandbox, browser E2E. Run `deploy/docker-compose.sandbox.yml` and repeat before release.
* **Apply locally:** `cd backend && .venv/bin/alembic upgrade head` (adds two indexes; your `basket_db` is still at `0020`).
* **New back-office rule:** shipments, return status and refunds need an admin JWT or `X-Internal-Service-Key`.

---


## 1. Project Identity, Problem Statement & Philosophy

### 1.1 What BASKET Is
**BASKET** is a full-featured, hyper-local multi-retailer e-commerce marketplace engineered specifically for the Indian commerce ecosystem. It unifies neighbourhood kiranas, specialty merchants, and regional retail outlets into a seamless consumer platform spanning:
- **Groceries & Essentials** (FMCG, dairy, fresh vegetables)
- **Fashion & Apparel** (clothing, footwear, multi-variant sizing)
- **Consumer Electronics** (appliances, gadgets, warranties)
- **Beauty & Lifestyle** (cosmetics, wellness, personal care)

### 1.2 Core Architectural Principles
- **Headless & Decoupled:** Async FastAPI (Python 3.12) backend serving a modern Next.js 15 (React 19) App Router frontend.
- **Fail-Safe Commerce:** Zero phantom stock via row-level transactional database locks (`SELECT ... FOR UPDATE`), cryptographic HMAC-SHA256 quotes with 5-minute expiry, and an atomic transactional outbox pattern.
- **Resilient Search:** OpenSearch 2.x primary faceted search backed by an automated circuit breaker with transparent fallback to PostgreSQL full-text search (`tsvector`).
- **Product Provenance:** Transparent Product Passports with an append-only, auditable claim review history.

---

## 2. Complete Inventory of What Is Built

### 2.1 Commit & Migration History
The repository has progressed through rigorous feature phases and audits. The database schema is cleanly maintained across 20 linear Alembic migrations:

| Phase | Description | Key Modules | Alembic Migrations | Status |
| :--- | :--- | :--- | :--- | :---: |
| **Phase 1** | Core Multi-Retailer Marketplace | Identity, Catalogue, Cart, Pricing, Inventory, Orders, Payments, Search, Admin/Retailer Portals | `0001` through `0015` | **100% Complete & Verified** |
| **Phase 2A**| Basket Mission Planner | Knapsack budget optimization, thematic clustering, cart sync | `0016_basket_mission` | **100% Complete & Verified** |
| **Phase 2B**| Substitute Intelligence | 5-tier explainable alternatives, comparison matrix, atomic cart item replacement | Leverages 0002 & 0004 | **100% Complete & Verified** |
| **Phase 2C**| Basket Intent Memory | Customer preference profiles, recurring intentions, strict opt-in consent | `0017_basket_intent_memory`, `0018_personalization_opt_in` | **100% Complete & Verified** |
| **Phase 2D**| Product Passport & Moderation | Canonical specifications, listing passports, claims moderation queue, and append-only review history | `0019_product_passport`, `0020_claim_review_history` | **100% Complete & Verified** (Commit `026f801`) |

### 2.2 Quality Assurance & Test Verification
Both backend and frontend test suites are fully automated, completely isolated, and currently green:
- **Backend Test Suite:** see §0 — runs on PostgreSQL via `DATABASE_URL` and mutates inventory rows; use a dedicated test DB. *(Pre-audit: 448 passed.)*
- **Frontend Test Suite:** `100 passed` (Node built-in test runner via `npm test`; API-client tests).
- **Static Analysis:** `ruff check .` (Python) and `npm run type-check` / `npm run lint` (TypeScript strict mode) pass with 0 errors.
- **Production Build:** `npm run build` succeeds cleanly across all 36 application routes.

---

## 3. What Developers Must Audit First & Critical Checklists

Before writing new features, developers should complete these three verification checks:

### 3.1 PR #31 Merge Verification
- **Branch:** `feature/phase-2d-product-passport` is up-to-date with remote (`026f801`).
- GitHub Actions CI for PR #31 is green.
- Confirm with the user before merging PR #31 into `integration`.
- Once merged, pull the latest `integration` branch and create a dedicated branch for Phase 3:
  ```bash
  git checkout integration
  git pull origin integration
  git checkout -b feature/phase-3-advanced-marketplace
  ```

### 3.2 Razorpay Production & Webhook Verification
- Review `backend/app/modules/payments/service.py` and `router.py`.
- **Sandbox Fallback:** Sandbox keys (`rzp_test_mock`) are permitted in development and automated testing.
- **Production Guard:** Ensure that when `ENVIRONMENT=production`, the application raises a fatal error at startup if `RAZORPAY_KEY_ID` or `RAZORPAY_KEY_SECRET` are missing or default to mock keys.
- **Webhook HMAC:** Confirm that `POST /api/v1/payments/webhook` always validates `X-Razorpay-Signature`.

### 3.3 Media Storage Enhancement (DISC-01)
- Currently, products and KYC documents store external string URLs.
- Implement an S3-compatible presigned upload endpoint (`/api/v1/media/presigned-url`) before mass onboarding real merchants.

---

## 4. Phase 3 Implementation Roadmap

The 9 approved Phase 3 features are detailed in `PHASE_3_FEATURE_TRACKER.md`. Here is the recommended implementation order:

```mermaid
flowchart TD
    M1[1. Price Intelligence & Historical Trends\nFeature 6 - 90-day price history & discount badges]
    M2[2. Bharat Multilingual\nFeature 8 - next-intl localization & Hindi/Tamil search]
    M3[3. Demand Gap & Unmet Demand\nFeature 1 - Zero-search aggregation & retailer alerts]
    M4[4. Basket Community Buying\nFeature 2 - Group purchasing & tier volume discounts]
    M5[5. Basket Community Exchange\nFeature 3 - Customer basket RFQs & retailer bidding]
    M6[6. AI Negotiator\nFeature 4 - Conversational cart discount assistant]
    M7[7. Dukaan vs Dukaan\nFeature 5 - 90-second multi-kirana live reverse auction]
    M8[8. Sale Stream\nFeature 7 - Live flash deals real-time feed]
    M9[9. Handwritten List to Basket\nFeature 9 - Vision OCR list to cart (Optional)]

    M1 --> M2 --> M3 --> M4 --> M5 --> M6 --> M7 --> M8 --> M9
```

> [!WARNING]
> **Explicit Restriction:**  
> "Sale Stream Rewind" has been permanently removed from the requirements. Do NOT implement Sale Stream Rewind.

---

## 5. Frontend Redesign Specifications (Blinkit-Inspired Quick-Commerce UI)

Following Phase 3 feature integration, the development team is tasked with executing a comprehensive UI refresh:

### 5.1 Design Tokens & Palette
- **Primary Yellow:** `#F8CB46` / `#FFDE59` (Hero sections, accent badges, delivery tags, quick CTAs).
- **Primary Green:** `#0C831F` / `#00A859` (Add to Cart buttons, pricing savings highlights, stock status, verified badges).
- **Neutral Dark:** `#1C1C1C` / `#222222` (High-contrast typography).
- **Card Background:** Pure white `#FFFFFF` with soft shadows (`shadow-sm` / `shadow-md`) against a light neutral page background `#F4F6F8`.
- **Identity Retention:** Preserve the existing **BASKET** logo, naming, and typography mark.

### 5.2 Micro-Interactions & Animation System
- **Add-to-Cart Micro-Interaction:** Subtle bouncing scale (`active:scale-95 transition-transform duration-150`) when incrementing item counts.
- **Mobile Floating Cart:** Sticky bottom pill showing item count, total price, and a "View Basket" sliding drawer CTA.
- **Skeleton Loading Screens:** Replace generic spinning wheels with realistic shimmer skeletons (`animate-pulse`) across all product cards, category grids, and checkout totals.
- **Image Optimization:** Use Next.js `<Image />` with fixed aspect ratios and blur placeholders.

---

## 6. Daily Development & Verification Commands

```bash
# -------------------------------------------------------------
# 1. BACKEND VERIFICATION
# -------------------------------------------------------------
cd backend

# Linting & Formatting
../backend/.venv/bin/ruff check .
../backend/.venv/bin/ruff format .

# Run Full Test Suite against a DEDICATED test database (fixtures mutate inventory)
DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/basket_audit_test .venv/bin/python -m pytest -q

# Check Database Migration Head
alembic current
alembic check

# -------------------------------------------------------------
# 2. FRONTEND VERIFICATION
# -------------------------------------------------------------
cd ../frontend

# TypeScript Type Check
npm run type-check

# ESLint Check
npm run lint

# Component & Unit Tests (100 tests)
npm test

# Production Build Verification (36 routes)
npm run build
```

---

## 7. Master Documentation Index

| Documentation File | Purpose |
| :--- | :--- |
| `PROJECT_ARCHITECTURE.md` | Comprehensive system design, data flows, security & outbox streaming |
| `BACKEND_AUDIT.md` | Module-by-module audit of all 13 backend modules & models |
| `API_INVENTORY.md` | Complete inventory of all 145 FastAPI endpoints and routes |
| `DISCREPANCY_REGISTER.md` | Register of known discrepancies, edge cases & technical debt |
| `PHASE_3_FEATURE_TRACKER.md` | Complete specification and schema blueprints for 9 Phase 3 features |
| `FRONTEND_BACKEND_STATUS.md` | Page-by-page audit of all 36 Next.js routes and integration status |
| `ARCHITECTURE.md` | Master platform architecture documentation |
| `IMPLEMENTATION_STATUS.md` | Master milestone tracking register |
| `README.md` | Quickstart guide and developer overview |
