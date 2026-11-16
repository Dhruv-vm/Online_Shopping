# BASKET — Task Breakdown and Ownership

> Fill in the two developer names/handles and ownership before parallel coding. This is a suggested split; adjust it to actual strengths, but keep shared foundation work coordinated.

## 1. Assign roles

| Responsibility | Owner |
|---|---|
| Integration owner | **Fill in** |
| Frontend foundation | **Fill in** |
| Backend foundation | **Fill in** |
| Database/Alembic migration owner | **Fill in one person** |
| Aiven account/service setup | **Fill in** |
| Demo/release owner | **Fill in** |

## 2. Phase 0 — jointly agree (do not parallelize prematurely)

- [ ] Create repository and `integration` branch.
- [ ] Add these project documents.
- [ ] Confirm stack and environment variable names.
- [ ] Agree API envelope, IDs, money representation, timestamps, pagination.
- [ ] Agree initial logical data model.
- [ ] Assign module/file ownership.
- [ ] Create `.env.example` with placeholders only.
- [ ] Establish lint, format, type-check, and test commands.

## 3. Phase 1 — shared foundation

Developer A:
- [ ] Next.js app shell and routing.
- [ ] Design tokens, layout, navigation, reusable UI patterns.
- [ ] Typed API client and global error/loading patterns.

Developer B:
- [ ] FastAPI app factory and versioned routing.
- [ ] Settings, logging, error handling, health/readiness.
- [ ] SQLAlchemy session and Alembic baseline.
- [ ] Initial tests and backend conventions.

Together:
- [ ] Connect to shared Aiven PostgreSQL.
- [ ] Validate migrations on a clean database.
- [ ] Freeze initial API/data contracts.
- [ ] Agree seed-data format and demo accounts.

Do not move to broad feature work until the foundation can start, connect, migrate, and pass smoke tests.

## 4. Phase 2 — mandatory commerce vertical slice

Suggested split:

Developer A:
- [ ] Catalogue browsing and product details UI.
- [ ] Search UI and filters.
- [ ] Cart UI and state integration.
- [ ] Checkout/order status UI.

Developer B:
- [ ] Catalogue and search API.
- [ ] OpenSearch indexing and search integration.
- [ ] Cart persistence and server-side validation.
- [ ] Inventory reservation, checkout, orders, payment sandbox boundary.

Joint:
- [ ] End-to-end browse → search → cart → checkout → order verification.
- [ ] Verify PostgreSQL is authoritative.
- [ ] Verify OpenSearch is used for actual search.

## 5. Phase 3 — Kafka and reliability

Assign one owner for each task:
- [ ] Transactional outbox schema and service.
- [ ] Outbox publisher to Kafka.
- [ ] Order-created event schema.
- [ ] Idempotent consumer.
- [ ] Consumer reaction (for example, update a read model/index or record a notification job).
- [ ] Retry/error handling and observability.
- [ ] Demonstrate duplicate event does not duplicate side effects.

## 6. Phase 4 — Sale Storm proof

- [ ] Create controlled test inventory.
- [ ] Run concurrent checkout attempts.
- [ ] Verify no oversell.
- [ ] Verify all-or-nothing multi-item reservation.
- [ ] Verify expiry releases stock once.
- [ ] Capture test output for demo.

## 7. Phase 5 — choose differentiators

Choose **one or two** based on remaining time and quality:

| Feature | Small credible slice |
|---|---|
| Quinn | Generate expiring quote; backend enforces discount floor |
| Apni Bhasha | Search across one or two tested languages |
| Basket Suggests | Compare same exact variant across two sellers |
| Demand Gap Radar | Aggregate zero-result searches by region/category |
| Basket Mission | Generate one editable cross-category shopping plan |
| Demand Exchange | One Demand Box and one retailer offer response |
| Product Proof | Show provenance and evidence for selected claims |
| BASKET LIVE | Voice input/output behind a provider adapter, only if verified |

## 8. Phase 6 — freeze and demo

- [ ] Stop adding features.
- [ ] Run clean setup and migration.
- [ ] Run automated tests and end-to-end smoke test.
- [ ] Verify PostgreSQL, Kafka, OpenSearch live behaviour.
- [ ] Test failure states and empty catalogue.
- [ ] Remove debug routes and secrets.
- [ ] Seed a predictable demo dataset.
- [ ] Rehearse the demo with a backup recording/screenshots.
- [ ] Merge only tested commits to `main`.
