# BASKET — Version 2.0 Local Setup & Run Guide

This guide details how to install, configure, and run BASKET Version 2.0 locally on your machine.

---

## 1. Prerequisites

- **macOS** or **Linux**
- **Node.js:** v20.x or v22.x LTS (Recommended: Node 22)
- **Python:** v3.12.x
- **PostgreSQL:** v16.x (Running locally on default port `5432`)
- **Cloudflared:** (Optional, for Razorpay test mode webhook tunneling)

---

## 2. Environment Configuration

BASKET reads configuration from `.env` files. Sample templates are available in `.env.example` and `backend/.env.example`.

### Backend Environment Variables (`backend/.env` or root `.env`)

```ini
ENVIRONMENT=development
DEBUG=false
PROJECT_NAME="BASKET Backend"
API_V1_STR=/api/v1
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# PostgreSQL (Use an isolated demo database like basket_c1_demo or basket_demo)
DATABASE_URL=postgresql+asyncpg://<username>@localhost:5432/basket_c1_demo
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=5
DATABASE_SSL_MODE=prefer

# Outbox & Event Dispatch (Set to direct for local zero-Kafka execution)
OUTBOX_DISPATCH=direct
SQL_ECHO=false

# Security
SECRET_KEY=insecure-default-development-key-change-in-production
JWT_SECRET_KEY=insecure-jwt-secret-key-change-in-production-min-256-bit
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
ALLOWED_HOSTS=["*"]

# Razorpay Test Credentials (Test Mode only)
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
# RAZORPAY_WEBHOOK_SECRET=...
```

---

## 3. Database Migration & Initialization

Run migrations using Alembic in the backend virtual environment:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Verify that the current head is at `0039_mission_completion`:
```bash
alembic current
```

---

## 4. Running the Application

To run the complete platform, start the services in 2 (or 3) terminals:

### Terminal 1 — Backend API (FastAPI)
```bash
cd backend
source .venv/bin/activate
export DATABASE_URL="postgresql+asyncpg://<username>@localhost:5432/basket_c1_demo"
export OUTBOX_DISPATCH="direct"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Probe: [http://localhost:8000/health](http://localhost:8000/health)
- Readiness Probe: [http://localhost:8000/ready](http://localhost:8000/ready)

### Terminal 2 — Frontend Application (Next.js 15)
```bash
cd frontend
npm run dev
```
- Web Application: [http://localhost:3000](http://localhost:3000)

### Terminal 3 (Optional) — Cloudflare Tunnel for Razorpay Webhooks
```bash
cloudflared tunnel --url http://localhost:8000
```
- Exposes your local backend to Razorpay so webhooks can be received at `/api/v1/payments/webhook`.

---

## 5. Verification Commands

Run the full automated test suite to confirm setup integrity:

```bash
# 1. Backend tests (runs in isolated *_test database)
cd backend && unset DATABASE_URL && .venv/bin/python -m pytest -q -p no:cacheprovider

# 2. Frontend integration tests
cd frontend && npm test

# 3. TypeScript type check
cd frontend && npm run type-check

# 4. Lint checks
cd backend && .venv/bin/ruff check .
cd frontend && npm run lint
```
