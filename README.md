# BASKET — Multi-Category Indian Retail Platform

> **Latest work (local, unpublished):** branch `feature/marketplace-completion` — storefront, 12-language interface (partial coverage), retailer onboarding, admin governance and Phase 3 completion. Migration head `0034_foreign_key_indexes`.
> Start with [`docs/MARKETPLACE_COMPLETION.md`](docs/MARKETPLACE_COMPLETION.md) (status, test results, limitations) and [`docs/EXTERNAL_CONFIGURATION.md`](docs/EXTERNAL_CONFIGURATION.md) (Razorpay, OCR, AI, storage). The version banner below describes the Phase 2D baseline.

## Running the marketplace-completion build

```bash
# Backend (from backend/) — demo database; OPENSEARCH_URL="" because the shared index belongs to basket_db
DATABASE_URL="$(grep -E '^DATABASE_URL=' .env | cut -d= -f2- | sed -E 's#/basket_db(\?|$)#/basket_demo\1#')" \
  OPENSEARCH_URL="" \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (from frontend/)
npm run build && npx next start -p 3000      # or: npm run dev
```

Demo accounts (`basket_demo` only, password `Basket@123`): `customer@basket.demo`, `retailer1…4@basket.demo`, `admin@basket.demo`. One sign-in page for all roles; the backend role decides where you land.

| Check | Command |
| --- | --- |
| Backend tests (isolated `*_test` DB) | `cd backend && unset DATABASE_URL && .venv/bin/python -m pytest -q -p no:cacheprovider` |
| Feature-by-feature API audit | `scripts/audit-features.sh` |
| Migration up/down verification | `scripts/verify-migrations.sh` |
| Lint | `cd backend && .venv/bin/ruff check .` · `cd frontend && npm run lint` |
| Frontend tests / types / build | `cd frontend && npm test && npm run type-check && npm run build` |
| Reset demo data | `scripts/reset-demo-db.sh` |
| Test-fixture quarantine | `cd backend && .venv/bin/python -m app.seeds.quarantine_test_data [--apply \| --list \| --restore BATCH]` |

---


> **Current Version:** `2.0.0` (Phase 2D Complete — Developer Handoff Baseline)  
> **Target Base Branch:** `integration`  
> **Active Feature Branch:** `feature/phase-2d-product-passport` (Commit: `026f801`, PR #31)  
> **Verification Status:** 448 Backend Tests Passed (100%), 100 Frontend Tests Passed (100%), 20 Migrations Applied (Head: `0020_claim_review_history`), 36 Routes Compiled, CI Green  

BASKET is an enterprise-grade, multi-category hyper-local e-commerce marketplace platform engineered for the Indian retail ecosystem (groceries & essentials, fashion & apparel, electronics, beauty & lifestyle).

---

## Master Documentation Suite

| Document | Description & Purpose |
|---|---|
| [`CLAUDE_DEVELOPER_HANDOFF.md`](CLAUDE_DEVELOPER_HANDOFF.md) | **Developer Handoff Guide:** Master takeover guide for Claude with Phase 3 roadmap and redesign specs. |
| [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) | **System Architecture:** Detailed system topology, security layers, HMAC quotes, outbox pattern, and data flows. |
| [`BACKEND_AUDIT.md`](BACKEND_AUDIT.md) | **Backend Module Audit:** Audit of all 13 business modules, ORM models, transaction safety, and test coverage. |
| [`API_INVENTORY.md`](API_INVENTORY.md) | **API Reference:** Comprehensive catalogue of all 145 FastAPI endpoints under `/api/v1`. |
| [`DISCREPANCY_REGISTER.md`](DISCREPANCY_REGISTER.md) | **Technical Debt & Discrepancies:** Edge cases, contract alignment, media storage, and payment safeguards. |
| [`PHASE_3_FEATURE_TRACKER.md`](PHASE_3_FEATURE_TRACKER.md) | **Phase 3 Roadmap:** Specifications, database schemas, and implementation blueprints for all 9 Phase 3 features. |
| [`FRONTEND_BACKEND_STATUS.md`](FRONTEND_BACKEND_STATUS.md) | **Frontend Audit:** Page-by-page audit across all 36 Next.js 15 App Router routes and Blinkit redesign plan. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **Core Architecture:** Historical architecture reference, module boundaries, and outbox streaming. |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | **Implementation Register:** Evidence-backed audit of all completed pull requests and database migrations. |
| [`CHANGELOG.md`](CHANGELOG.md) | **Project Changelog:** Release history following Keep a Changelog standards. |
| [`docs/product/ONLINE_SHOPPING_FEATURES.md`](docs/product/ONLINE_SHOPPING_FEATURES.md) | **Feature Specifications:** Master source of truth for Admin, Retailer, and Customer capabilities. |
| [`docs/SANDBOX_DEPLOYMENT_RUNBOOK.md`](docs/SANDBOX_DEPLOYMENT_RUNBOOK.md) | **Deployment Runbook:** Operational staging and deployment runbooks. |

---

## Core Technology Stack

### Frontend (`frontend/`)
- **Framework:** Next.js 15.5.29 (App Router) on Node.js 22 LTS
- **UI & Components:** React 19.0.0, Tailwind CSS v4, Radix UI accessible primitives, Lucide React
- **Language:** TypeScript with strict mode
- **Client Networking:** Centralized typed client (`lib/api.ts`) with Double-Submit CSRF integration
- **Test Suite:** Vitest / React Testing Library (100 component & integration tests)

### Backend (`backend/`)
- **Framework:** FastAPI modular monolith on Python 3.12.14
- **ORM & Migrations:** SQLAlchemy 2.0.38 (asyncio / asyncpg) + Alembic (20 migrations applied, head `0020_claim_review_history`)
- **Validation & Settings:** Pydantic v2 + Pydantic Settings
- **Authentication:** Argon2id password hashing + HTTP-only secure JWT cookies (HS256)
- **ASGI Server:** Uvicorn with lifespan management
- **Code Quality:** pytest, pytest-asyncio (448 unit/integration tests), Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** PostgreSQL 16 (`basket_db`) — single authoritative source of truth
- **Event Bus:** Apache Kafka with `SASL_SSL` and `SCRAM-SHA-256`
- **Search Engine:** OpenSearch 2.x with faceted filters (`basket_products_v1`) and transparent PostgreSQL FTS fallback
- **Payment Gateway:** Razorpay dual-mode sandbox & live server verification with HMAC webhook signing

---

## Quickstart & Local Setup

### 1. One-Command Bootstrap
```bash
./scripts/dev-setup.sh
```

### 2. Manual Startup

#### Backend API
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/ready`
- Prometheus Metrics: `http://localhost:8000/metrics`

#### Frontend Storefront
```bash
cd frontend
npm run dev
```
- Storefront URL: `http://localhost:3000`

---

## Quality Assurance & Verification Commands

```bash
# Backend checks (from backend/)
pytest -v                               # Run all 448 unit & integration tests
ruff check app tests alembic            # Lint code
ruff format --check app tests alembic   # Check formatting
alembic current                         # Confirm migration head (0020_claim_review_history)

# Frontend checks (from frontend/)
npm test                                # Run all 100 integration tests
npm run type-check                      # Strict TypeScript type check
npm run lint                            # Next.js ESLint check
npm run build                           # Production build check (36 routes)
```
```
