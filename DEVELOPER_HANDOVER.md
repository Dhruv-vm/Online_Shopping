# BASKET — Master Developer Handover Guide

> **Target Audience:** Incoming Software Engineers, Technical Leads & System Maintainers  
> **Repository:** [https://github.com/Rahul2006MILLION/Online_Shopping](https://github.com/Rahul2006MILLION/Online_Shopping)  
> **Base Branch:** `integration` (commit `16a3003`)  
> **Current Version:** `0.5.0` (Phase 4 Verified Baseline)  
> **Date:** 2026-11-19  

---

## 1. Executive Summary & Welcome

Welcome to the **BASKET** engineering team.

BASKET is an enterprise-grade multi-category online retail platform built for an expanding Indian retail chain. It combines high-reliability e-commerce foundations (modular monolith, transactional outbox, all-or-nothing atomic inventory reservations, and server-side payment verification) with a comprehensive three-role platform vision (**Admin**, **Retailer**, and **Customer / Purchaser**).

This guide is designed to get you from zero to a fully operational, test-verified local environment in under 15 minutes, with complete clarity on architectural guardrails, coding standards, and operational runbooks.

---

## 2. Verified Repository Baseline

```text
Current Branch Baseline:     origin/integration (commit 16a3003)
Latest PR Merged:            PR #18 (fix(orders): resolve post-checkout order visibility)
Alembic Migration Head:      0011_order_postpurchase (11 applied migrations, exactly 1 head)
Backend Test Suite:          361 tests passed, 0 failed (pytest -v)
Frontend Test Suite:         63 tests passed, 0 failed (npm test)
TypeScript Compilation:      Clean (0 errors via tsc --noEmit)
Next.js Production Build:    All 12 routes compiled cleanly
Ruff Code Quality:           100% passed (ruff check & ruff format --check)
CI Status:                   BASKET CI (GitHub Actions) all checks green
```

---

## 3. Technology Stack Summary

### Frontend (`frontend/`)
- **Runtime & Framework:** Node.js 22 LTS with Next.js 15.5 (App Router)
- **UI Library:** React 19, Tailwind CSS, shadcn/ui accessible primitives
- **Language:** TypeScript 5.x (`strict: true`, `noImplicitAny: true`)
- **State & Context:** React Context (`AuthContext`, `CartContext`)
- **Client Networking:** Centralized typed client (`lib/api/client.ts`) with custom `ApiClientError`, automatic 401 refresh deduplication, and Double-Submit CSRF integration

### Backend (`backend/`)
- **Runtime & Framework:** Python 3.12 with FastAPI
- **ORM & Migrations:** SQLAlchemy 2.x (asyncio) with Alembic
- **Validation & Configuration:** Pydantic v2 with Pydantic Settings
- **ASGI Server:** Uvicorn with lifespan management
- **Code Quality:** pytest, pytest-asyncio, Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** PostgreSQL 16 (`basket_db` on localhost:5432)
- **Event Bus:** Aiven Apache Kafka with `SASL_SSL` and `SCRAM-SHA-256` (`ca.pem` in `infra/aiven/certs/`)
- **Search Engine:** Aiven OpenSearch 2.x with blue/green alias routing (`basket_products_v1`)
- **Payments:** Razorpay Test Mode with server-side capture and HMAC webhook verification

---

## 4. Local Environment Bootstrap (Step-by-Step)

### Option A: One-Command Automated Bootstrap
From the repository root:
```bash
./scripts/dev-setup.sh
```

### Option B: Manual Setup

#### 1. Backend Setup
```bash
cd backend

# Create Python 3.12 virtual environment using uv or venv
uv venv --python 3.12 .venv
source .venv/bin/activate

# Install dependencies in editable mode
uv pip install -e ".[dev]"

# Configure environment variables
cp .env.example .env

# Verify database connection and apply all 11 migrations
alembic upgrade head
```

#### 2. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Configure environment variables
cp .env.example .env.local
```

---

## 5. Startup Commands & Services

### 1. Start Backend API
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/ready`
- Prometheus Metrics: `http://localhost:8000/metrics`

### 2. Start Frontend Storefront
```bash
cd frontend
npm run dev
# Or for production server:
npm run build && npm start
```
- Storefront URL: `http://localhost:3000`

---

## 6. Testing & Quality Assurance Workflows

Always run the full test suite before committing or creating a pull request:

### Backend Checks
```bash
cd backend
source .venv/bin/activate

# 1. Run all 361 pytest unit and integration tests
pytest -v

# 2. Run Ruff linter
ruff check app tests alembic

# 3. Run Ruff format check
ruff format --check app tests alembic

# 4. Confirm single Alembic head
alembic heads
```

### Frontend Checks
```bash
cd frontend

# 1. Run all 63 unit and API client integration tests
npm test

# 2. Strict TypeScript type-check
npm run type-check

# 3. Next.js production build check
npm run build
```

### One-Command Full Repository Verification
```bash
./scripts/verify-environment.sh
```

---

## 7. Key Architectural Invariants ("Rules of the Road")

1. **PostgreSQL Is Authoritative:**
   - PostgreSQL is the sole system of record.
   - Never trust prices, taxes, or stock quantities sent by the browser. Re-evaluate authoritative product and inventory state in the checkout transaction.
2. **OpenSearch Is a Derived Projection:**
   - OpenSearch is an asynchronous, eventually consistent search index.
   - OpenSearch must never authorize a purchase or determine inventory availability.
   - If OpenSearch fails, the built-in 3-state circuit breaker transparently fails over to PostgreSQL `tsvector` full-text search.
3. **Transactional Outbox for Event Emission:**
   - Never perform a direct "dual-write" to PostgreSQL and Kafka.
   - Write business mutations and outbox events in a single ACID transaction. The outbox publisher handles dispatching to Kafka with lease fencing.
4. **All-or-Nothing Atomic Reservations:**
   - Multi-item checkout reservations lock inventory rows atomically in sorted order (`ORDER BY listing_id ASC`) to eliminate concurrency deadlocks during flash sales ("Sale Storm").
5. **Double-Submit Cookie CSRF Defense:**
   - Mutating HTTP requests (`POST`, `PATCH`, `DELETE`) require the `X-CSRF-Token` header to match the `XSRF-TOKEN` cookie issued by the server.
6. **Anti-IDOR Isolation:**
   - Customers can only view or mutate their own resources.
   - Protected order endpoints enforce strict `customer_id` matching, or require an unguessable guest access token (`gat_...`).

---

## 8. Common Operational Runbooks

### Runbook 1: Managing Database Migrations
- Always branch from `integration`.
- Author migrations using `alembic revision -m "description"`.
- Ensure both `upgrade()` and `downgrade()` functions are fully implemented and testable.
- Ensure `alembic heads` shows **exactly one head**. Merging branching migrations into `integration` without a merge migration is prohibited.

### Runbook 2: Working with Aiven Kafka SASL_SSL
- The Kafka cluster uses `SASL_SSL` with `SCRAM-SHA-256`.
- The CA certificate is placed at `infra/aiven/certs/ca.pem` (never commit this certificate).
- When writing tests that verify Kafka configuration or authentication, **always use the temporary PEM fixture pattern** (see `tests/test_config.py`), which generates a syntactically valid temporary certificate fixture locally. Never rely on the real external file being present on CI runners.

### Runbook 3: Razorpay Sandbox Payments
- Dual-mode architecture:
  - Local tests use the mocked cryptographic HMAC engine in `tests/test_payments.py`.
  - Authentic sandbox rehearsals use genuine credentials (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) entered into `.env`.
- Never modify database payment records directly to fake a successful provider capture.
- Webhooks must pass HMAC signature verification (`X-Razorpay-Signature`).

---

## 9. Git & Contribution Workflow

1. Always branch from `integration`:
   ```bash
   git checkout integration
   git pull origin integration
   git checkout -b feature/your-feature-name
   ```
2. Commit with standard Conventional Commits: `feat(...)`, `fix(...)`, `docs(...)`, `test(...)`, `style(...)`.
3. Push to `origin` and open a Pull Request targeting `integration`, never `main`.
4. Ensure all CI checks (Backend Lint/Format/Test, Frontend Type-Check/Test/Build) pass before requesting code review.
