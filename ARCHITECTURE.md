# BASKET — Technical Architecture

> **Architecture Style:** Modular Monolith with Event-Driven Outbox & Asynchronous Search Projections  
> **Status:** Active System Architecture  
> **Last Audited:** 2026-11-19T17:30:00+05:30  
> **Base Branch:** `integration`  

---

## 1. System Topology

BASKET uses a **modular monolith** for the HTTP application layer, combined with a transactional outbox publisher and independently runnable Kafka consumers and workers. Operational complexity is minimized by avoiding distributed service boundaries prematurely, while enforcing strict module-level separation.

```text
       +-----------------------------------------------------------+
       |             Client Layer (Next.js 15 App Router)          |
       |  +--------------------+ +-------------------+ +---------+ |
       |  | Customer Storefront| |   Retailer Portal | |Admin GUI| |
       |  +--------------------+ +-------------------+ +---------+ |
       +-----------------------------------------------------------+
                                     |
                                HTTPS / JSON
                                     v
       +-----------------------------------------------------------+
       |             FastAPI Modular Monolith Core Layer           |
       |  +-----------------------------------------------------+  |
       |  | API Router (/api/v1/*) & Dependency Injection       |  |
       |  +-----------------------------------------------------+  |
       |  | Domain Modules:                                     |  |
       |  |  • Identity & RBAC (Argon2id, Sessions, CSRF)       |  |
       |  |  • Catalogue & Storefront (Products, Variants, SKU) |  |
       |  |  • Cart & Merging (Guest sessions, Cart items)      |  |
       |  |  • Pricing & Quotes (Discounts, Tax, HMAC quotes)   |  |
       |  |  • Inventory (All-or-nothing stock locking, leases) |  |
       |  |  • Orders & Post-Purchase (Snapshots, Tracking, RTN)|  |
       |  |  • Payments (Razorpay Sandbox, HMAC webhooks)       |  |
       |  |  • Search & Circuit Breaker (OpenSearch + SQL FTS)  |  |
       |  +-----------------------------------------------------+  |
       |  | Security & Governance: Double-Submit CSRF, Anti-IDOR |  |
       +-----------------------------------------------------------+
              |                                          |
       Atomic Transactions                    Asynchronous Projection
              |                                          |
              v                                          v
+-------------------------------+       +-----------------------------------+
|      Aiven PostgreSQL 16      |       |      Aiven OpenSearch 2.x         |
|  (Authoritative System of     |       | (Derived, Rebuildable Projection) |
|   Record: 33 Relational       |       |  • Index: basket_products_v1      |
|   Commerce Entities)          |       |  • Read Alias: ..._search         |
|                               |       |  • Write Alias: ..._write         |
|  • outbox_events              |       +-----------------------------------+
|  • consumer_inbox             |                         ^
+-------------------------------+                         |
       |                                                  |
       | (SELECT ... FOR UPDATE SKIP LOCKED)              |
       v                                                  |
+-------------------------------+                         |
|   Outbox Publisher Daemon     |                         |
|  (Lease-fenced background)    |                         |
+-------------------------------+                         |
       |                                                  |
    SASL_SSL (SCRAM-SHA-256)                              |
       v                                                  |
+-------------------------------+                         |
|      Aiven Apache Kafka       |                         |
|  (Event Bus: order.events,    |                         |
|   inventory.events, etc.)     |                         |
+-------------------------------+                         |
       |                                                  |
       v                                                  |
+-------------------------------+                         |
|  Incremental Indexer Consumer |-------------------------+
| (Strategy B: external_gte)    |
+-------------------------------+
```

---

## 2. Fixed Technology Choices

### Frontend
- **Framework:** Next.js 15 (App Router) on Node.js 22 LTS
- **UI & Components:** React 19, Tailwind CSS, shadcn/ui accessible primitives
- **Language:** TypeScript with strict mode (`strict: true`, `noImplicitAny: true`)
- **Animation:** Framer Motion (purposeful micro-interactions only)
- **API Client:** Centralized typed API client (`frontend/lib/api/client.ts`) with custom `ApiClientError` and Double-Submit CSRF integration

### Backend
- **Language & Framework:** Python 3.12 with FastAPI
- **ORM & Migrations:** SQLAlchemy 2.x (asyncio) with Alembic
- **Validation & Settings:** Pydantic v2 with Pydantic Settings
- **ASGI Server:** Uvicorn with lifespan management
- **Code Quality & Testing:** pytest, pytest-asyncio, Ruff (linting & formatting)

### Infrastructure & External Services
- **System of Record:** PostgreSQL 16 (local sandbox and Aiven cloud)
- **Event Bus:** Aiven Apache Kafka with SASL_SSL and SCRAM-SHA-256
- **Search Engine:** Aiven OpenSearch 2.x with 3-state circuit breaker and PostgreSQL SQL fallback
- **Payment Gateway:** Razorpay Sandbox API with server-side HMAC webhook and capture verification

---

## 3. Backend Module Boundaries

The backend enforces strict modular monolith boundaries. Each module in `backend/app/modules/` owns its domain router, service layer, repository/data-access code, Pydantic schemas, and private database models:

```text
backend/app/
├── api/v1/                   # Unified API router aggregating all domain routers
├── core/
│   ├── config.py             # Pydantic Settings loading from environment
│   ├── database.py           # SQLAlchemy async engine, session factory, test fallbacks
│   ├── exceptions.py         # Standardized AppException hierarchy & error codes
│   ├── logging.py            # Structured JSON logger with request_id propagation
│   ├── metrics.py            # Thread-safe Prometheus metrics registry (/metrics)
│   ├── search/               # OpenSearch client, IndexManager, CircuitBreaker, Consumer
│   └── consumer/             # Kafka consumer factory, BaseConsumer, lease manager
├── modules/
│   ├── identity/             # Users, sessions, Argon2id passwords, customer addresses
│   ├── catalogue/            # Products, categories, variants, retailers, stores, listings
│   ├── cart/                 # Persistent guest/customer carts, item mutations, cart merging
│   ├── pricing/              # Platform/retailer discounts, multi-item taxes, HMAC quotes
│   ├── inventory/            # Store inventory, row-level locks, all-or-nothing reservations
│   ├── orders/               # Orders, item snapshots, tracking, cancellations, returns
│   ├── payments/             # Dual-mode Razorpay client, verification, webhooks, refunds
│   ├── search/               # Universal search endpoint, DSL generator, suggestions
│   └── notifications/        # In-app customer notification center
├── events/
│   ├── schemas.py            # Pydantic domain event envelopes & payload models
│   ├── publisher.py          # Transactional outbox publisher with lease fencing
│   └── outbox.py             # Outbox repository & event serialization
└── main.py                   # FastAPI application factory, lifespan, CORS, middleware
```

### Module Invariants:
1. **No Circular Imports:** Dependency flows strictly from routers $\rightarrow$ services $\rightarrow$ repositories $\rightarrow$ database models.
2. **Business Rules in Services:** Route handlers perform HTTP parsing and status dispatch only; domain invariants live in service classes.
3. **Cross-Module Interactions:** Modules interact via service method calls within the same transaction or asynchronously via domain events emitted through the outbox.

---

## 4. Multi-Role Platform Architecture & RBAC

As defined in [`FEATURE_SPECIFICATION.md`](FEATURE_SPECIFICATION.md), BASKET operates across three distinct roles:

```text
+--------------------------------------------------------------------------------+
|                           Role-Based Access Control                            |
+--------------------------------------------------------------------------------+
|  Role      | Target Surface   | Scope of Authority                             |
|:-----------|:-----------------|:-----------------------------------------------|
| ADMIN      | Admin Panel      | Platform catalogue, category taxonomy, global  |
|            | (/admin/*)       | deals, retailer KYC approval, commission rates,|
|            |                  | dispute resolution, marketplace analytics.     |
|------------+------------------+------------------------------------------------|
| RETAILER   | Retailer Portal  | Store profile, own listings, variant prices,   |
|            | (/retailer/*)    | own inventory, order fulfillment, returns,     |
|            |                  | participation in Dukaan vs Dukaan & Demand.    |
|------------+------------------+------------------------------------------------|
| CUSTOMER   | Storefront       | Discovery, cart, checkout quotes, orders,      |
|            | (/orders, etc.)  | tracking, returns, notifications, Mission,     |
|            |                  | Substitute Intelligence, Community Buying.     |
+--------------------------------------------------------------------------------+
```

### RBAC Enforcement Rules:
- **Server-Side Enforcement:** Every protected endpoint validates the caller's role (`ADMIN`, `RETAILER`, `CUSTOMER`) and resource ownership. Frontend route hiding alone is strictly prohibited.
- **Retailer Tenant Scoping:** Retailers cannot view or mutate another retailer's listings, inventory, orders, or pricing.
- **Anti-IDOR Protection:** Order details (`/api/v1/orders/{id}`) enforce strict customer ID ownership matching, or require a cryptographically unguessable guest access token (`gat_...`).

---

## 5. Data Authority & Invariants

| Data Domain | Single Authority | Secondary Projections | Consistency Model | Notes |
|---|---|---|---|---|
| **Product Master** | PostgreSQL | OpenSearch `basket_products_v1` | Eventual (Outbox $\rightarrow$ Kafka) | Canonical source for approved attributes. |
| **Search Projections** | OpenSearch | PostgreSQL `tsvector` Fallback | Eventual | Derived index; never validates checkout or stock. |
| **Product Prices** | PostgreSQL | OpenSearch documents | Transactional | Client price is untrusted; re-fetched in quote/checkout. |
| **Store Inventory** | PostgreSQL | OpenSearch `in_stock` flag | Immediate Transactional | Locked with `SELECT ... FOR UPDATE` row locks. |
| **Carts** | PostgreSQL | Browser localStorage (cache only)| Immediate | Guest-to-customer merging revalidates live stock. |
| **Checkout Quotes** | PostgreSQL | Signed HMAC Client Token | 5-minute expiry | Line-item CGST/SGST/IGST tax breakdowns. |
| **Reservations** | PostgreSQL | None | Expiring (10 minutes) | All-or-nothing stock locking across multi-item cart. |
| **Orders** | PostgreSQL | Outbox events $\rightarrow$ Kafka | Transactional state machine | Contains immutable item and address snapshots. |
| **Payment Facts** | PostgreSQL | Provider Dashboard | Verified Provider Webhook | Trigger-protected immutable capture ledger entries. |
| **Domain Events** | PostgreSQL `outbox_events` | Kafka Broker | Guaranteed At-Least-Once | Published by lease-fenced outbox daemon. |
| **Consumer Deduplication** | PostgreSQL `consumer_inbox` | None | Exactly-Once Side Effects | Scoped by `(consumer_group, event_id)`. |

---

## 6. Transactional Outbox Pattern & Event Streaming

To eliminate dual-write race conditions and distributed rollback failures, BASKET implements the Transactional Outbox pattern:

```text
[HTTP Checkout Request]
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│               PostgreSQL ACID Transaction                   │
│                                                             │
│  1. Deduct Store Inventory (reserved_quantity += quantity)  │
│  2. Create Order & Immutable OrderItem Snapshots            │
│  3. Insert Transactional Outbox Event (outbox_events)        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
          │ (Commit)
          ▼
┌─────────────────────────────────────────────────────────────┐
│              Outbox Publisher Background Daemon             │
│                                                             │
│  • SELECT ... FOR UPDATE SKIP LOCKED                        │
│  • Acquire 30s durable lease (lease_id, lease_expires_at)   │
│  • Publish JSON event to Kafka Broker (SASL_SSL)            │
│  • On Broker ACK: UPDATE outbox_events SET published=True   │
│  • On Failure: Exponential backoff & lease release          │
└─────────────────────────────────────────────────────────────┘
          │ (Kafka Network Dispatch)
          ▼
┌─────────────────────────────────────────────────────────────┐
│                 Asynchronous Consumer Group                 │
│                                                             │
│  • Receive Kafka Message                                    │
│  • Check consumer_inbox for (consumer_group, event_id)      │
│  • If present: Skip side-effect (Idempotent Deduplication)  │
│  • If absent: Execute side-effect & INSERT consumer_inbox   │
│  • Commit Kafka Offset                                      │
└─────────────────────────────────────────────────────────────┘
```

### Event Envelope Specification
Every event emitted across Kafka follows this strict Pydantic envelope:
```json
{
  "event_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_type": "order.created",
  "event_version": "1.0",
  "occurred_at": "2026-11-19T11:48:00.123456Z",
  "aggregate_type": "order",
  "aggregate_id": "699db156-b6cc-46f8-8a51-fbdc05919304",
  "correlation_id": "req_88f9104b2a3d",
  "payload": {
    "order_number": "BSK-20261119-17B02CFD",
    "customer_id": "689608b5-3448-465b-a378-06c0e615fcbe",
    "total_payable_paise": 359800,
    "currency": "INR",
    "item_count": 2
  }
}
```

---

## 7. Inventory & Checkout Safety ("Sale Storm" Invariants)

1. **Client Price and Stock Are Untrusted:**
   - The browser never dictates unit price, tax rate, or availability.
   - Prices and taxes are calculated exclusively on the server during quote generation and re-validated at order placement.
2. **All-or-Nothing Atomic Reservations:**
   - Multi-item carts are evaluated atomically. If 4 items are in stock but the 5th item is unavailable, the entire reservation fails without locking partial inventory.
3. **Sorted Row Locks:**
   - Inventory rows are locked in sorted order (`ORDER BY listing_id ASC`) to prevent concurrent circular deadlocks across simultaneous checkouts.
4. **Configurable Reservation Expiry:**
   - Active reservations hold stock for 10 minutes. An automated background worker reconciles and releases expired unpurchased stock.
5. **Idempotent Checkout Submissions:**
   - `POST /api/v1/orders` requires an `Idempotency-Key` header. Identical keys return the cached order response without creating duplicate database rows.

---

## 8. Search Resilience & Circuit Breaker Architecture

OpenSearch handles discovery queries, while PostgreSQL maintains data authority:

1. **Blue/Green Indexing:** Versioned indices (`basket_products_v1`) are fronted by alias pointers (`basket_products_search`). Full re-indexing can run in background without query disruption.
2. **Circuit Breaker States:**
   - **`CLOSED`:** Normal operation. Search queries execute against OpenSearch.
   - **`OPEN`:** OpenSearch failures reached threshold ($\ge 5$). Requests fast-fail immediately to PostgreSQL full-text search fallback.
   - **`HALF_OPEN`:** After a 30-second recovery window, probe requests check OpenSearch health. If successful, resets to `CLOSED`.
3. **PostgreSQL Fallback Guardrails:**
   - The fallback query executes `tsvector` matching over canonical product attributes.
   - Fallback protects database CPU by omitting expensive facet aggregations and capping page size to $\le 20$.

---

## 9. Security & Identity Invariants

1. **Credential Hygiene:**
   - Secrets are loaded exclusively from environment variables (`.env`).
   - `.env`, certificate files (`.pem`), and private keys (`.key`) are explicitly git-ignored.
2. **Double-Submit Cookie CSRF Protection:**
   - Safe HTTP methods (`GET`, `HEAD`, `OPTIONS`) do not require CSRF validation.
   - Mutating methods (`POST`, `PATCH`, `DELETE`) require the request header `X-CSRF-Token` to match the value of the `XSRF-TOKEN` cookie.
   - Bearer token requests via `Authorization: Bearer <token>` are exempt from CSRF checks.
3. **Immutable Financial Facts:**
   - Payment capture records in `payment_captures` are protected by PostgreSQL database triggers that raise exceptions on `UPDATE` or `DELETE`.
4. **Safe Error Envelopes:**
   - Application exceptions return structured JSON: `{ "error": { "code": "...", "message": "...", "request_id": "...", "details": [] } }`.
   - Stack traces, internal SQL strings, and sensitive credentials are never leaked in client responses.

---

## 10. Basket Substitute Intelligence Architecture (Phase 2B)

Phase 2B extends the marketplace with an intelligent product substitution engine that discovers and recommends suitable alternatives to products in customer baskets or on product detail pages.

### 10.1 Core Substitution Tiers
Substitutes are classified into 5 explainable tiers:
1. **`CLOSEST_MATCH`:** Product in the same category with identical or nearest specifications, matching brand, and closest price delta.
2. **`BUDGET_FRIENDLY`:** Equivalent category product priced $\ge 5\%$ lower (or $\ge$ ₹100 lower) with core utility parity.
3. **`BETTER_VALUE`:** Top-rated seller ($\ge 4.5$★) with competitive pricing ($\le 105\%$ of original) and high specification overlap.
4. **`PREMIUM_UPGRADE`:** Elevated brand or enhanced attribute model priced higher ($> 105\%$ of original).
5. **`AVAILABLE_NOW`:** Triggered when the original listing is out-of-stock or inactive, surfacing alternative in-stock options for immediate dispatch.

### 10.2 Marketplace Invariants
- **Category Isolation:** Candidates must strictly match the original product's `category_id`.
- **Authenticity & Verification:** Only active listings from active, `VERIFIED` retailers are considered.
- **Explainability:** Every recommendation computes `matching_specs`, `differing_specs`, `price_diff_paise`, `savings_percentage`, `similarity_score`, seller rating, and compatibility notes.
- **Cart Replacement:**
  - `POST /api/v1/cart/items/{item_id}/replace` requires customer consent.
  - Validates cart ownership (anti-IDOR) and category consistency.
  - Automatically merges quantities if the target listing is already present in the basket (capped at 10 and available stock).
  - Supersedes active checkout quotes (`QuoteStatus.SUPERSEDED`) to prevent stale pricing checkouts.

---

## 11. Basket Intent Memory Architecture (Phase 2C)

Phase 2C introduces a customer-controlled memory system that remembers shopping preferences and recurring intentions across the entire multi-retailer marketplace.

### 11.1 Domain Models & Migration 0017 / 0018
- **`CustomerPreferenceProfile` (`customer_preference_profiles`):**
  - Attached 1:1 to `users.id` via foreign key with `ON DELETE CASCADE`.
  - Captures structured preferences: `preferred_brands` (JSONB list), `preferred_categories` (JSONB list), `preferred_retailers` (JSONB list), `preferred_price_range` (JSONB object), `preferred_attributes` (JSONB object), `shopping_priorities` (JSONB list of `ShoppingPriority`), and `category_preferences` (JSONB object).
  - Explicit customer consent flag: `personalization_enabled` (`BOOLEAN`, default `False` — strict opt-in).
- **`RecurringIntention` (`recurring_intentions`):**
  - Customer-defined recurring shopping targets (title, category IDs, frequency enum, budget in paise, notes, active status, last execution timestamp).
  - **Zero Auto-Order Invariant:** Recurring intentions strictly serve as planning suggestions and memory anchors. The platform never places orders, charges payment methods, or reserves stock automatically.
- **`IntentMemoryItem` (`intent_memory_items`):**
  - Granular, explainable memory items (memory type, key, structured value, natural language summary, source provenance `CUSTOMER_STATED` / `MISSION_DERIVED` / `SYSTEM_SUGGESTED`, active flag).

### 11.2 Privacy, Personalization Consent & Explainability Guardrails
1. **Tenant Isolation & Anti-IDOR:** All intent queries and mutations strictly filter by `current_user.id`. Customer A cannot access or mutate Customer B's profile, recurring intentions, or memories.
2. **Strict Opt-In Default & Consent Toggle (`PATCH /api/v1/intent/consent`):**
   - Personalization defaults to `False` (opt-in) across models, schemas, repositories, and migrations.
   - Creating or editing a preference profile never silently enables personalization.
   - When `personalization_enabled` is `False`, all recommendation boosts in Mission Planning and Substitute Discovery are bypassed.
   - Suggestions API returns empty recommendation lists and neutral explanations.
3. **Transparent Personalization:**
   - When a substitute or mission item receives an intent score boost (e.g. for matching a preferred brand), the recommendation reason explicitly states the rationale (e.g. `"Recommended because you prefer 'Apple' in your saved intent memory."`).
   - Availability, real inventory, pricing validity, verified retailer status, and statutory HSN tax classification are never overridden by intent memory.
4. **Complete Customer Control & Erasure (`DELETE /api/v1/intent/clear-all`):**
   - Customers can delete individual memories or trigger a full wipe of all intent records via their account dashboard.

---

## 12. Phase 2D: Product Passport Architecture

### 12.1 Overview & Domain Isolation
Basket Product Passport provides a transparent, auditable product-information record that helps customers understand what a product is, which claims have been verified by administration, what evidence supports those claims, and which details are specific to an individual retailer's listing.

The architecture enforces strict separation between **canonical product-level facts** and **retailer-listing-specific facts**:
- **Product-Level Passport (`product_passports`):**
  - Associated 1:1 with `products.id`.
  - Holds canonical facts: Manufacturer, Country of origin, Model number, GTIN/EAN/UPC, Material composition, Technical specifications, Package contents, Manufacturer warranty terms, Care/safety instructions, and Certifications.
  - Edited only by authorized administrative users (`PUT /api/v1/admin/passport/products/{id}`).
- **Retailer Listing Passport (`listing_passports`):**
  - Associated 1:1 with `product_listings.id`.
  - Captures seller-specific details: Item condition (`NEW`, `REFURBISHED`, `OPEN_BOX`, `PRE_OWNED`), Seller warranty terms, Packaging notes, and Fulfillment/dispatch notes.
  - Retailer mutations are strictly scoped to listings owned by the authenticated retailer (`retailer_id == current_retailer.id`). One retailer can never overwrite canonical product facts or another retailer's listing details.
- **Traceable Claims & Evidence (`passport_claims` & `passport_claim_review_histories`):**
  - Stores granular assertions (e.g. FSSAI license, BIS certification, Agmark grade, organic compliance).
  - Tracks complete audit provenance: `submitted_by_user_id`, `review_status` (`PENDING`, `VERIFIED`, `REJECTED`), `reviewed_by_user_id`, `reviewed_at`, `rejection_reason`, `evidence_url`, `evidence_type`, and `is_public_evidence`.
  - Auditable claim review history (`passport_claim_review_histories`) maintains an append-only ledger of every administrative verification and rejection, preserving previous rejection reasons, timestamps, reviewer IDs, and revision snapshots across claim edits.

### 12.2 Verification Lifecycle & Trust Rules
1. **Unconditional `PENDING` Default:** All claims submitted by retailers start as `PENDING`. Retailers cannot approve their own claims.
2. **Mandatory Admin Rejection Reason:** Admins can reject invalid claims with a required non-empty `rejection_reason`, which is visible to the submitting retailer to explain required corrections.
3. **Audit-Preserving Re-Review Trigger on Edit:** Updating any previously verified or rejected claim transitions the active claim state back to `PENDING`. Crucially, previous review decisions, rejection reasons, reviewer notes, and historical timestamps are never destroyed or overwritten; they are preserved in `passport_claim_review_histories` (migration `0020_claim_review_history`).
4. **Customer Privacy & Redaction:**
   - Public customer responses (`GET /api/v1/products/{id}/passport`) only expose `evidence_url` if `is_public_evidence` is `True` **AND** `review_status` is `VERIFIED`.
   - Internal admin notes, reviewer IDs, submitter IDs, and rejection reasons are strictly stripped from all customer-facing payloads.
   - Customers never see pending or rejected claims represented as verified facts.
5. **Safe Empty Fallback:** Products without an active passport return a safe empty schema containing product metadata and available seller offers without throwing 404 or breaking catalogue browsing.
6. **Public Listing Visibility Invariant:** Public listing passports are only returned if the parent product is active, the retailer is verified and active, and the listing itself is active.

---

## 13. System Audit & Master Documentation Index

Comprehensive audit reports and developer handoff specifications are maintained across dedicated documentation modules:
- [PROJECT_ARCHITECTURE.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/PROJECT_ARCHITECTURE.md): Complete architecture, security, concurrency, and data models.
- [BACKEND_AUDIT.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/BACKEND_AUDIT.md): Module-by-module audit of all 13 backend modules, models, and test verification.
- [API_INVENTORY.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/API_INVENTORY.md): Comprehensive catalogue of all 145 API endpoints under `/api/v1`.
- [DISCREPANCY_REGISTER.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/DISCREPANCY_REGISTER.md): Register of known discrepancies, edge cases, and technical debt.
- [PHASE_3_FEATURE_TRACKER.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/PHASE_3_FEATURE_TRACKER.md): Approved Phase 3 feature specifications and implementation roadmap.
- [FRONTEND_BACKEND_STATUS.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/FRONTEND_BACKEND_STATUS.md): Page-by-page audit of all 36 Next.js routes and integration status.
- [CLAUDE_DEVELOPER_HANDOFF.md](file:///Users/dhruv/dhruv%20files/basket/Online_Shopping/CLAUDE_DEVELOPER_HANDOFF.md): Master developer handoff guide and execution checklist for Claude.




