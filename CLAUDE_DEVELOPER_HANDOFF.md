# BASKET — Comprehensive Developer Handoff Guide for Claude

> **Target Agent:** Claude (Principal Full-Stack Engineer & Architect)  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Workspace Path:** `/Users/dhruv/dhruv files/basket/Online_Shopping`  
> **Current Feature Branch:** `feature/phase-2d-product-passport` (Latest Commit: `026f801`)  
> **Target Base Branch:** `integration`  
> **Handoff Date:** 2026-11-20  

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
- **Backend Test Suite:** `448 passed` (`pytest`, SQLite async in-memory simulation, zero mutation of production records).
- **Frontend Test Suite:** `100 passed` (`vitest`, testing React 19 App Router components).
- **Static Analysis:** `ruff check .` (Python) and `npm run type-check` / `npm run lint` (TypeScript strict mode) pass with 0 errors.
- **Production Build:** `npm run build` succeeds cleanly across all 36 application routes.

---

## 3. What Claude Must Audit First & Critical Checklists

Before writing new features, Claude should complete these three verification checks:

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

Following Phase 3 feature integration, Claude is tasked with executing a comprehensive UI refresh:

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

# Run Full Test Suite (448 tests)
PYTHONPATH=. pytest -v

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
