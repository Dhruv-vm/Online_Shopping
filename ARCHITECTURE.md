# BASKET — Technical Architecture

## 1. Architecture style

Use a **modular monolith** for the HTTP backend, plus independently runnable Kafka consumers/workers. Keep module boundaries explicit without introducing distributed services prematurely.

```text
Customer / Retailer / Admin
          |
          v
Next.js + TypeScript frontend
          |
      HTTPS / JSON
          |
          v
FastAPI modular monolith
  |       |         |
  |       |         +--> External adapters (Razorpay sandbox, optional voice provider)
  |       |
  |       +--> Transactional outbox
  |
  +--> Aiven PostgreSQL (system of record)
          |
          +--> Outbox publisher --> Aiven Kafka --> Consumers
          |                                      |
          |                                      +--> OpenSearch indexer
          |                                      +--> Notifications / analytics (if implemented)
          |
          +--> Inventory / orders / reservations

Frontend product search --------------------------> OpenSearch
Checkout validation ------------------------------> PostgreSQL only
```

## 2. Fixed technology choices

### Frontend
- Next.js (App Router)
- TypeScript with strict mode
- Tailwind CSS
- shadcn/ui where useful
- Framer Motion only for purposeful interactions
- A single typed API client and centralized error handling

### Backend
- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic migrations
- Pydantic schemas
- pytest

### Infrastructure
- Aiven PostgreSQL
- Aiven Apache Kafka
- Aiven OpenSearch
- Razorpay Sandbox only if credentials and callback verification are configured

Do not add Redis, another database, Kubernetes, or a new framework without a written architecture decision.

## 3. Backend module boundaries

Suggested modules:

```text
backend/app/
  api/v1/
  core/                 # settings, security, logging, errors
  db/                   # engine, session, base
  modules/
    users/
    retailers/
    catalogue/
    search/
    inventory/
    cart/
    checkout/
    orders/
    payments/
    reservations/
    demand/              # optional
    negotiation/         # optional
  events/
    schemas/
    outbox/
    publisher/
  workers/
  tests/
```

Each module owns its routes, schemas, service logic, and repository/data-access code. Avoid circular imports. Keep business rules in services, not route handlers.

## 4. Frontend boundaries

```text
frontend/
  app/
  components/
    ui/
    layout/
  features/
    catalogue/
    search/
    cart/
    checkout/
    orders/
    admin/
    optional-feature/
  lib/
    api/
    auth/
    config/
    validation/
  types/
```

Feature-specific components belong in their feature folder. Shared UI belongs in `components`. Do not create one giant page or one global component containing all feature logic.

## 5. Data authority and consistency

| Data | Authority | Notes |
|---|---|---|
| Product identity and approved attributes | PostgreSQL | Canonical record |
| Search document | OpenSearch | Rebuildable, eventually consistent |
| Price | PostgreSQL | Revalidate during checkout |
| Inventory | PostgreSQL | Atomic conditional update/locking |
| Cart | PostgreSQL | Client values are untrusted |
| Order | PostgreSQL | Transactional state machine |
| Reservation | PostgreSQL | Expiring, idempotent lifecycle |
| Payment state | PostgreSQL + verified provider callback | Never trust client success redirect |
| Domain event | Outbox row, then Kafka | Outbox is durable publication intent |

## 6. Transactional outbox and Kafka

When a business transaction creates an order:
1. Validate cart, price, and stock in PostgreSQL.
2. Reserve inventory and create order/payment intent in one database transaction.
3. Insert an outbox event in that same transaction.
4. Commit.
5. A publisher reads unpublished outbox rows and publishes to Kafka.
6. Mark an outbox row published only after broker acknowledgement.
7. Consumer processes the event idempotently and records processed event IDs.

If publishing fails, retry from the outbox. Do not pretend a database commit and Kafka publish are one atomic transaction.

### Event envelope

Every event should carry:
- `event_id` (UUID)
- `event_type`
- `event_version`
- `occurred_at` (UTC ISO-8601)
- `aggregate_type`
- `aggregate_id`
- `correlation_id`
- `payload`

Use the order ID as Kafka message key for order lifecycle events. Consumers must tolerate duplicate delivery.

## 7. Inventory and checkout safety

- Never trust price or stock sent by the browser.
- Re-fetch authoritative product/listing/price/inventory data in the checkout transaction.
- Use atomic conditional updates or row locks.
- For a multi-item cart, reserve all items in one transaction; if any item cannot be reserved, roll back the entire reservation attempt.
- Do not hold database locks while waiting for a payment provider.
- Use a short reservation expiry (for example, 10 minutes; make it configurable).
- An expiry worker releases expired reservations exactly once.
- Use idempotency keys for checkout and payment operations.
- Verify payment webhooks/signatures on the server.
- Model payment success, failure, and pending states explicitly.

## 8. Search indexing

- Product search queries go to OpenSearch.
- Catalogue writes go to PostgreSQL.
- Approved catalogue changes emit an outbox event.
- An indexer consumes events and updates OpenSearch.
- Indexing must be idempotent and support retry/rebuild.
- Search results can be stale. Product detail and checkout must revalidate price and availability from PostgreSQL.

## 9. Product ingestion lifecycle (optional feature)

```text
Authorized source / retailer file
       -> source adapter
       -> raw staging
       -> validation and normalization
       -> duplicate/variant resolution
       -> human review queue
       -> approve / reject / request correction
       -> canonical product + retailer listing
       -> outbox event
       -> Kafka
       -> OpenSearch index
```

Preserve source, source URL/reference, ingestion time, and relevant evidence. Do not merge variants based on name similarity alone.

## 10. AI and voice boundaries

- Quinn is the bounded negotiation/business assistant, not the voice provider.
- A voice provider such as Gnani is optional and must be behind an adapter.
- Confirm provider capabilities, language support, streaming, interruption handling, and commercial terms before relying on them.
- LLM output is an untrusted proposal. Backend services enforce price floors, quote expiry, user permissions, stock, and transaction rules.
- Never give an LLM direct SQL access or unrestricted mutation tools.

## 11. Security baseline

- Secrets only in environment variables / secret manager; never commit `.env`.
- Validate all request bodies with Pydantic.
- Enforce authorization on the server for every protected operation.
- Use parameterized ORM queries.
- Apply request size limits to uploads.
- Validate file type and content; do not trust file extension.
- Avoid logging passwords, tokens, payment secrets, or sensitive personal data.
- Use HTTPS for deployed services.
- CORS must list explicit allowed origins.
- Rate-limit sensitive endpoints where feasible.
- Keep audit records for privileged catalogue and price actions.

## 12. Deployment and local development

Use environment-based configuration. Provide `.env.example` with placeholder values only. Provide health/readiness endpoints that distinguish application health from dependency readiness.

Keep local development possible with documented setup instructions. Do not make the application silently fall back to fake production data when an external service is unavailable.
