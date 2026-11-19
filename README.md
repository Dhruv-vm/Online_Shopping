# BASKET — Multi-Category Indian Retail Platform

> **Current Version:** `0.5.0` (Phase 4 Verified Baseline)  
> **Target Base Branch:** `integration`  
> **Stable Release Branch:** `main`  
> **Verification Status:** 361 Backend Tests Passed (100%), 63 Frontend Tests Passed (100%), 11 Migrations Applied (1 Head), CI Green  

BASKET is an enterprise-grade, multi-category online retail platform engineered for an Indian retail chain expanding across multi-state operations (groceries, personal care, electronics, fashion, and home essentials).

---

## Master Documentation Suite

| Document | Description & Purpose |
|---|---|
| [`PROJECT_MASTER.md`](PROJECT_MASTER.md) | **Master Control Document:** System overview, governance rules, and documentation index. |
| [`FEATURE_SPECIFICATION.md`](FEATURE_SPECIFICATION.md) | **Finalized Product Specification:** Complete feature scope across Admin, Retailer, and Customer roles. |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | **Verified Codebase Audit:** Evidence-backed audit of all implemented phases (Phases 0–4, PR #1 through PR #18). |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | **Technical Architecture:** System topology, module boundaries, data authority, and event streaming. |
| [`INFRASTRUCTURE_STATUS.md`](INFRASTRUCTURE_STATUS.md) | **Infrastructure Status Matrix:** Live status of PostgreSQL, Kafka, OpenSearch, and Razorpay. |
| [`CHANGELOG.md`](CHANGELOG.md) | **Project Changelog:** Release history following Keep a Changelog standards. |
| [`DEVELOPER_HANDOVER.md`](DEVELOPER_HANDOVER.md) | **Developer Handover Guide:** Step-by-step developer onboarding, bootstrap runbooks, and testing workflows. |
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | **Engineering Roadmap:** Prioritized backlog for Phase 5 (Multi-Role Panels), Phase 6, and Phase 7. |

---

## Core Technology Stack

### Frontend (`frontend/`)
- **Framework:** Next.js 15.5 (App Router) on Node.js 22 LTS
- **UI & Components:** React 19, Tailwind CSS, shadcn/ui accessible primitives
- **Language:** TypeScript with strict mode
- **Client Networking:** Centralized typed client (`lib/api/client.ts`) with custom `ApiClientError` and Double-Submit CSRF integration

### Backend (`backend/`)
- **Framework:** FastAPI modular monolith on Python 3.12
- **ORM & Migrations:** SQLAlchemy 2.x (asyncio) + Alembic (11 migrations applied, single head `0011_order_postpurchase`)
- **Validation & Settings:** Pydantic v2 + Pydantic Settings
- **ASGI Server:** Uvicorn with lifespan management
- **Code Quality:** pytest, pytest-asyncio, Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** PostgreSQL 16 (`basket_db` on localhost:5432) — single authoritative source of truth
- **Event Bus:** Aiven Apache Kafka with `SASL_SSL` and `SCRAM-SHA-256` (`infra/aiven/certs/ca.pem`)
- **Search Engine:** Aiven OpenSearch 2.x with blue/green alias routing (`basket_products_v1`) and transparent PostgreSQL SQL fallback
- **Payment Gateway:** Razorpay Test Mode with server-side capture and HMAC webhook verification

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
pytest -v                               # Run all 361 unit & integration tests
ruff check app tests alembic            # Lint code
ruff format --check app tests alembic   # Check formatting
alembic heads                           # Confirm single migration head

# Frontend checks (from frontend/)
npm test                                # Run all 63 integration tests
npm run type-check                      # Strict TypeScript type check
npm run build                           # Production build check (12 routes)

# Full repository verification gate (from root)
./scripts/verify-environment.sh
```
