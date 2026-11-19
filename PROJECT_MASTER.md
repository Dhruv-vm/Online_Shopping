# BASKET — Project Master Control & Governance Document

> **Repository:** [https://github.com/Rahul2006MILLION/Online_Shopping](https://github.com/Rahul2006MILLION/Online_Shopping)  
> **Target Base Branch:** `integration`  
> **Stable Release Branch:** `main`  
> **Current Version:** `0.5.0` (Phase 4 Verified Baseline)  
> **Last Audited:** 2026-11-19T17:30:00+05:30  
> **Status:** All Phase 0–4 Commerce Pipelines, Event Streaming, Search Projections, and Post-Purchase Features Implemented, Tested, and Merged.

---

## 1. Executive Overview

BASKET is an enterprise-grade, multi-category online retail platform engineered for an Indian retail chain expanding across multi-state operations (groceries, electronics, fashion, and home essentials).

The repository serves two foundational purposes:
1. **A Fully Implemented, Production-Ready Commerce Core (Phases 0–4):**
   - Complete end-to-end purchasing pipeline: Browse catalogue $\rightarrow$ Search $\rightarrow$ Persistent Cart $\rightarrow$ HMAC Quotes $\rightarrow$ Atomic Inventory Reservation $\rightarrow$ Order Creation $\rightarrow$ Razorpay Sandbox Payment $\rightarrow$ Post-Purchase Tracking, Cancellations, and Returns.
   - Event-driven architecture with Transactional Outbox, Aiven Kafka (SASL_SSL / SCRAM-SHA-256), and Aiven OpenSearch with circuit breaker and PostgreSQL SQL fallback.
   - Comprehensive test suite: **361 backend pytest tests passing**, **63 frontend integration tests passing**, **11 Alembic migrations applied**, Next.js 15 production build clean, and GitHub Actions CI passing green.
2. **A Finalized Three-Role Platform Specification & Roadmap:**
   - Formalized roles: **Admin**, **Retailer**, and **Customer / Purchaser**.
   - Advanced shopping and demand intelligence features: **Basket Mission**, **Substitute Intelligence**, **Demand Gap Radar**, **Community Buying**, and **Dukaan vs Dukaan**.

---

## 2. Master Documentation Index

All project documentation is strictly organized and reconciled across these core documents:

| Document | Primary Audience | Purpose & Scope |
|---|---|---|
| [`FEATURE_SPECIFICATION.md`](FEATURE_SPECIFICATION.md) | Product Managers & Engineers | Finalized product specification across Admin, Retailer, and Customer roles. Kept strictly separate from implementation status. |
| [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) | Technical Leads & Auditors | Verified, code-backed implementation audit detailing exactly what is built, tested, and merged into `integration` (PR #1 through PR #18). |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System Architects & Developers | System topology, modular monolith boundaries, data authority, event contracts, transactional outbox pattern, and security invariants. |
| [`INFRASTRUCTURE_STATUS.md`](INFRASTRUCTURE_STATUS.md) | DevOps & Platform Engineers | Live status matrix for PostgreSQL, Kafka, OpenSearch, Razorpay Sandbox, and container sandboxes. |
| [`CHANGELOG.md`](CHANGELOG.md) | All Contributors | Chronological release history from Phase 0 foundation through Phase 4 post-purchase and order visibility fixes. |
| [`DEVELOPER_HANDOVER.md`](DEVELOPER_HANDOVER.md) | Incoming Developers | Complete onboarding guide, local environment bootstrap, runbooks, testing workflows, and operational guardrails. |
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | Engineering Team | Prioritized engineering roadmap detailing immediate (Phase 5), medium-term (Phase 6), and long-term (Phase 7) implementation tasks. |
| [`DATA_MODEL.md`](DATA_MODEL.md) | Database Developers | Canonical entity relationships, schemas, and Alembic migration rules. |
| [`API_CONTRACTS.md`](API_CONTRACTS.md) | Frontend & Backend Engineers | OpenAPI schemas, endpoint contracts, idempotency headers, and error envelopes. |
| [`DECISIONS.md`](DECISIONS.md) | Technical Leadership | Architecture Decision Records (ADRs) tracking structural technical choices. |

---

## 3. Core Architecture & Invariant Principles

1. **PostgreSQL Is the Single System of Record:**
   - Authoritative for catalogue, prices, inventory, reservations, carts, orders, and payment facts.
   - Client-provided prices, discounts, and inventory counts are untrusted and re-validated server-side in every transactional boundary.
2. **Dual-Mode Razorpay Sandbox Integration:**
   - Real provider order creation and capture verification via authenticated Razorpay API keys (`rzp_test_...`).
   - Server-side HMAC-SHA256 signature verification on verify endpoints and webhooks (`X-Razorpay-Signature`).
   - Strict separation between local cryptographic test simulation and authentic external gateway calls. Direct database state mutations to simulate external success are prohibited.
3. **Reliable Event Streaming via Transactional Outbox:**
   - Domain events are written to `outbox_events` within the same database transaction as business state mutations.
   - The outbox publisher uses `SELECT ... FOR UPDATE SKIP LOCKED` with durable leases to eliminate race conditions.
   - Aiven Kafka uses SASL_SSL authentication with SCRAM-SHA-256 and CA certificate validation.
   - Consumer reliability enforces exactly-once side-effect execution via `consumer_inbox` deduplication tables.
4. **Derived OpenSearch Projections with SQL Fallback:**
   - OpenSearch is a rebuildable, asynchronous projection populated by catalogue consumers.
   - OpenSearch never determines stock availability or checkout validity.
   - A 3-state circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) transparently routes queries to PostgreSQL `tsvector` full-text search fallback when OpenSearch is unavailable.
5. **Strict Security Baseline:**
   - Argon2id password hashing with modern memory/time hardness.
   - HTTP-only authentication cookies paired with Double-Submit Cookie CSRF protection (`XSRF-TOKEN` cookie + `X-CSRF-Token` header).
   - Strict Anti-IDOR (Insecure Direct Object Reference) tenant isolation: authenticated users and guest access tokens can only access their own resources.
   - Zero credentials or private certificates committed to version control.

---

## 4. Current Quality & Verification Metrics

```
Branch Baseline:             origin/integration (commit 16a3003)
Latest PR Merged:            PR #18 (fix(orders): resolve post-checkout order visibility)
Alembic Migration Revisions: 11 applied migrations (single head: 0011_order_postpurchase)
Backend Test Suite:          361 tests passed, 0 failed (100% pytest pass rate)
Frontend Test Suite:         63 tests passed, 0 failed (100% Node test runner pass rate)
TypeScript Compilation:      0 errors (tsc --noEmit clean)
Next.js Production Build:    12/12 routes compiled cleanly
Ruff Code Quality:           100% passed (ruff check & ruff format --check clean)
GitHub Actions CI:           BASKET CI all checks passing green
```

---

## 5. Repository Layout

```text
Online_Shopping/
├── frontend/                     # Next.js 15 (App Router) + React 19 + Tailwind CSS
│   ├── app/                      # App router pages: /, /cart, /checkout, /orders, /account, etc.
│   ├── components/               # UI components, layout, system status
│   ├── lib/api/                  # Centralized typed API client and unit tests
│   ├── types/                    # Shared TypeScript interfaces
│   └── package.json
├── backend/                      # FastAPI modular monolith application
│   ├── app/
│   │   ├── api/v1/               # Versioned API routes & dependency injection
│   │   ├── core/                 # Config, database engine, logging, metrics, exceptions
│   │   ├── modules/              # Domain modules: catalogue, identity, cart, pricing,
│   │   │                         # inventory, orders, payments, search, etc.
│   │   └── main.py               # Application factory & lifespan
│   ├── alembic/                  # 11 database migration versions
│   ├── tests/                    # 361 pytest unit & integration tests
│   └── pyproject.toml
├── docs/                         # Additional runbooks and setup guides
├── infra/                        # Aiven setup templates and certificates
├── scripts/                      # Bootstrap and verification scripts
├── FEATURE_SPECIFICATION.md      # Finalized product specification across 3 roles
├── IMPLEMENTATION_STATUS.md      # Verified codebase audit (Phases 0–4)
├── ARCHITECTURE.md               # Technical architecture & boundaries
├── INFRASTRUCTURE_STATUS.md      # Infrastructure status matrix
├── CHANGELOG.md                  # Release history
├── DEVELOPER_HANDOVER.md         # Master developer onboarding guide
├── NEXT_STEPS.md                 # Prioritized engineering backlog
└── README.md                     # Project quickstart
```
