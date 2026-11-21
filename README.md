# BASKET — Multi-Category Indian Retail Platform

> **Release:** **BASKET Version 2.0**  
> **Active Feature Branch:** `feature/version-2-development`  
> **Baseline Release:** `v1.0` (`68ac8ff`, preserved and unmodified)  
> **Proposed Release Tag:** `v2.0`  
> **Verification Status:** 604 Backend Tests Passed (100%), 129 Frontend Tests Passed (100%), 39 Migrations Applied (Head: `0039_mission_completion`), 56 Next.js App Router Routes Compiled, All Migration Rollbacks Verified, CI Green.

BASKET is an enterprise-grade, multi-category hyper-local e-commerce marketplace platform engineered for the Indian retail ecosystem (groceries & essentials, fashion & apparel, electronics, beauty & lifestyle).

---

## Master Documentation Suite

### Version 2.0 Release Documentation
| Document | Description & Purpose |
|---|---|
| [`BASKET_V2_RELEASE_NOTES.md`](BASKET_V2_RELEASE_NOTES.md) | **Version 2.0 Release Notes:** Official release report, delivered capabilities, quality gates, and architecture enhancements. |
| [`BASKET_V2_FINAL_AUDIT.md`](BASKET_V2_FINAL_AUDIT.md) | **Final Technical Audit:** Evidence-backed verification across Customer, Retailer, Admin, and Infrastructure. |
| [`BASKET_V2_KNOWN_LIMITATIONS.md`](BASKET_V2_KNOWN_LIMITATIONS.md) | **Known Limitations & Dependencies:** Honest status of i18n coverage, external API keys, and auto-debit mandates. |
| [`BASKET_V2_SETUP_GUIDE.md`](BASKET_V2_SETUP_GUIDE.md) | **Setup & Run Guide:** Local configuration, database setup, environment variables, and startup commands. |
| [`BASKET_V2_DEMO_GUIDE.md`](BASKET_V2_DEMO_GUIDE.md) | **Product Demonstration Runbook:** Role-by-role presentation scripts, demo accounts, and end-to-end user journeys. |
| [`BASKET_V2_HANDOFF.md`](BASKET_V2_HANDOFF.md) | **Engineering Handoff:** Architecture guidelines and boundaries for the incoming Branding, UI, and UX phase. |

### Technical & Historical Reference
| Document | Description & Purpose |
|---|---|
| [`RELEASE_NOTES_V1.0.md`](RELEASE_NOTES_V1.0.md) | **Version 1.0 Release Notes:** Baseline Round 1 submission report and platform capabilities. |
| [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) | **System Architecture:** Topology, security layers, HMAC quotes, outbox pattern, and data flows. |
| [`BACKEND_AUDIT.md`](BACKEND_AUDIT.md) | **Backend Module Audit:** Audit of all 13 business modules, ORM models, transaction safety, and test coverage. |
| [`API_INVENTORY.md`](API_INVENTORY.md) | **API Reference:** Comprehensive catalogue of FastAPI endpoints under `/api/v1`. |
| [`DISCREPANCY_REGISTER.md`](DISCREPANCY_REGISTER.md) | **Technical Debt & Discrepancies:** Register of edge cases, contract alignments, and payment safeguards. |
| [`VERSION_2_FEATURE_TRACKER.md`](VERSION_2_FEATURE_TRACKER.md) | **Version 2 Feature Tracker:** Evidence-based status register of all Version 2.0 items. |
| [`CHANGELOG.md`](CHANGELOG.md) | **Project Changelog:** Release history following Keep a Changelog standards. |

---

## Core Technology Stack

### Frontend (`frontend/`)
- **Framework:** Next.js 15.5.29 (App Router) on Node.js 22 LTS
- **UI & Components:** React 19.0.0, Tailwind CSS v4, Radix UI accessible primitives, Lucide React
- **Language:** TypeScript with strict type checking
- **Client Networking:** Centralized typed client (`lib/api.ts`) with Double-Submit CSRF integration
- **Real-Time Client:** Shared `EventSource` (SSE) client (`lib/realtime.ts`) with focus-refresh
- **Test Suite:** Vitest / Node Test Runner (129 component & integration tests)

### Backend (`backend/`)
- **Framework:** FastAPI modular monolith on Python 3.12
- **ORM & Migrations:** SQLAlchemy 2.0.38 (asyncio / asyncpg) + Alembic (39 migrations applied, head `0039_mission_completion`)
- **Validation & Settings:** Pydantic v2 + Pydantic Settings
- **Authentication:** Argon2id password hashing + HTTP-only secure JWT cookies (HS256)
- **ASGI Server:** Uvicorn with lifespan management
- **Code Quality:** pytest, pytest-asyncio (604 unit/integration tests), Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** PostgreSQL 16 (`basket_db` / `basket_c1_demo`) — authoritative source of truth
- **Transactional Outbox:** Dual-mode: Direct dispatch (`OUTBOX_DISPATCH=direct`) or Apache Kafka
- **Search Engine:** OpenSearch 2.x with per-database index prefixes and transparent PostgreSQL FTS fallback
- **Payment Gateway:** Razorpay dual-mode sandbox with server-side capture, webhook HMAC verification, and refund reconciliation

---

## Quickstart & Local Setup

### 1. Manual Startup

#### Terminal 1 — Backend API
```bash
cd backend
source .venv/bin/activate
export DATABASE_URL="postgresql+asyncpg://<username>@localhost:5432/basket_c1_demo"
export OUTBOX_DISPATCH="direct"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive API Docs: `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/ready`

#### Terminal 2 — Frontend Storefront & Portals
```bash
cd frontend
npm run dev
```
- Application URL: `http://localhost:3000`

#### Terminal 3 (Optional) — Webhook Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

---

## Quality Assurance & Verification Commands

```bash
# 1. Full Backend Test Suite (isolated test database)
cd backend && unset DATABASE_URL && .venv/bin/python -m pytest -q -p no:cacheprovider

# 2. Feature-by-Feature API Audit (16 areas)
./scripts/audit-features.sh

# 3. Database Migration Up/Down/Rollback Verification
./scripts/verify-migrations.sh

# 4. Code Quality & Linting
cd backend && .venv/bin/ruff check .
cd frontend && npm run lint

# 5. Frontend Tests, Types, and Production Build
cd frontend
npm test
npm run type-check
npm run build
```
