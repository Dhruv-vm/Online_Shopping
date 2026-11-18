# BASKET — Project Control Centre

BASKET is a multi-category online retail platform for an Indian retail chain. This repository is designed for a two-developer team working exclusively in **Google Antigravity**, with ChatGPT used for architecture, prompt preparation, reviews, and debugging.

## Read these first

1. [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) — product scope and non-negotiable priorities.
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — system boundaries and technical architecture.
3. [`AGENT_RULES.md`](AGENT_RULES.md) — mandatory instructions for both Antigravity agents.
4. [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md) — the shared communication log between developers/agents.
5. [`DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md) — Git branches, integration, and daily workflow.
6. [`QUALITY_GATES.md`](QUALITY_GATES.md) — definition of done and release gates.
7. [`TASK_BREAKDOWN.md`](TASK_BREAKDOWN.md) — suggested ownership and implementation sequence.

## Source of truth

- Product scope: `PROJECT_CHARTER.md`
- Architecture: `ARCHITECTURE.md`
- Shared interfaces: `API_CONTRACTS.md`
- Data ownership: `DATA_MODEL.md`
- Decisions: `DECISIONS.md`
- Cross-agent coordination: `AGENT_HANDOFF.md`

If two documents conflict, stop and record the conflict in `AGENT_HANDOFF.md`. Do not silently choose one. The integration owner resolves it and records the decision in `DECISIONS.md`.

## Quality principle

**A small, complete, tested, demonstrable vertical slice is better than many unfinished features.** Mandatory commerce flow and real use of PostgreSQL, Kafka, and OpenSearch take priority over optional AI features.

---

## Technology Stack

### Frontend
- **Framework:** Next.js 15 (App Router)
- **UI & State:** React 19, Tailwind CSS, shadcn/ui primitives
- **Language:** TypeScript with strict mode
- **Animation:** Framer Motion (purposeful micro-interactions only)
- **Client:** Centralized typed API client with structured error handling

### Backend
- **Framework:** FastAPI (Modular Monolith)
- **ORM & Migrations:** SQLAlchemy 2.x (async) + Alembic
- **Validation & Settings:** Pydantic v2 + Pydantic Settings
- **Server:** Uvicorn (ASGI)
- **Quality & Testing:** pytest, pytest-asyncio, Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** Aiven PostgreSQL (orders, inventory, reservations, prices, users)
- **Event Bus:** Aiven Apache Kafka (order domain events via Transactional Outbox)
- **Search Engine:** Aiven OpenSearch (derived product search index)
- **Payments:** Razorpay Sandbox (server-side webhook and signature verification)

---

## Monorepo Repository Structure

```text
basket/
├── frontend/                     # Next.js 15 frontend application
│   ├── app/                      # App router pages, layouts, globals
│   ├── components/               # UI components (shadcn/ui & shared)
│   ├── features/                 # Modular feature domains
│   ├── lib/                      # Centralized API client and utilities
│   ├── types/                    # Shared TypeScript types
│   ├── package.json
│   └── .env.example
├── backend/                      # FastAPI modular monolith application
│   ├── app/
│   │   ├── api/                  # Versioned API routes (/api/v1) & dependencies
│   │   ├── core/                 # Config, database engine, logging, exceptions
│   │   ├── modules/              # Domain modules (catalogue, cart, orders, etc.)
│   │   └── main.py               # Application factory & lifespan
│   ├── alembic/                  # Database migration versions and harness
│   ├── tests/                    # Pytest test suite
│   ├── pyproject.toml
│   └── .env.example
├── docs/                         # Architecture diagrams and specifications
├── infra/                        # Aiven infrastructure setup templates
│   ├── aiven/
│   └── .env.example
├── scripts/                      # Bootstrap and verification scripts
│   ├── dev-setup.sh              # One-command developer bootstrap
│   └── verify-environment.sh     # Comprehensive foundation verification
├── README.md                     # Project control centre (this file)
├── PROJECT_CHARTER.md            # Vision, scope, and non-negotiables
├── ARCHITECTURE.md               # System boundaries and data authority
├── AGENT_RULES.md                # Mandatory agent guardrails and conventions
├── AGENT_HANDOFF.md              # Shared communication and sync log
├── API_CONTRACTS.md              # Baseline OpenAPI and REST interfaces
├── DATA_MODEL.md                 # Entity relationships and migration rules
├── DEVELOPMENT_WORKFLOW.md       # Git branches, PRs, and worktree routines
├── TASK_BREAKDOWN.md             # Role assignments and phase tracking
├── QUALITY_GATES.md              # Definition of Done and gate criteria
└── DECISIONS.md                  # Architecture Decision Records (ADRs)
```

---

## Prerequisites

- **Git:** >= 2.40
- **Node.js:** >= 20.x (Node 22 LTS recommended)
- **npm:** >= 10.x
- **Python:** Python 3.12 (managed via `uv` or `venv`)
- **uv:** `>= 0.11` (for ultra-fast Python virtualenv and dependency installation)
- **PostgreSQL Client (Optional):** `libpq` / `psql` if manual CLI querying is needed

---

## Local Setup Instructions

### 1. Quick Bootstrap (One Command)
Run the automated bootstrap script from the repository root:
```bash
./scripts/dev-setup.sh
```

### 2. Manual Setup

#### Backend Setup
```bash
cd backend
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
```

#### Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env.local
```

---

## Environment Configuration

Both backend and frontend load settings from environment files. Templates with placeholders are provided:

- `backend/.env.example` -> `backend/.env`
  - `DATABASE_URL`: Aiven PostgreSQL connection URL with `sslmode=require`.
  - `SECRET_KEY`: Cryptographically secure random secret key (minimum 32 characters).
  - `CORS_ORIGINS`: Allowed client origins (`["http://localhost:3000"]`).
  - `KAFKA_*` & `OPENSEARCH_*`: Aiven service parameters.
- `frontend/.env.example` -> `frontend/.env.local`
  - `NEXT_PUBLIC_API_URL`: Backend URL (defaults to `http://localhost:8000`).

> **Security Note:** Never commit `.env` or `.env.local` files containing real secrets to source control.

---

## Startup Commands

### Start Backend Development Server
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
- API Base: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/health`
- Readiness Endpoint: `http://localhost:8000/ready`

### Start Frontend Development Server
```bash
cd frontend
npm run dev
```
- Storefront & Control Panel: `http://localhost:3000`

---

## Testing & Quality Assurance Commands

### Backend Checks
```bash
cd backend
source .venv/bin/activate

# Run Pytest suite
pytest -v

# Run Ruff linter
ruff check .

# Run Ruff formatter check
ruff format --check .

# Inspect Alembic migration heads
alembic heads
```

### Frontend Checks
```bash
cd frontend

# Run TypeScript strict type-check
npm run type-check

# Run Next.js linter
npm run lint

# Build production bundle
npm run build
```

### Full Repository Verification Gate
To run all verification checks across both frontend and backend in one command:
```bash
./scripts/verify-environment.sh
```
