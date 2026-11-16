# BASKET — Architecture Decision Record (ADR) Log

Record material architecture decisions here. New decisions are appended; do not erase historical context. Use `AGENT_HANDOFF.md` for proposals and discussion, then record accepted decisions here.

## Decision template

### ADR-NNN — Short title
- **Status:** PROPOSED / ACCEPTED / SUPERSEDED
- **Date:**
- **Decision owner:**
- **Context:**
- **Decision:**
- **Alternatives considered:**
- **Consequences/trade-offs:**
- **Related PR / handoff entry:**

---

## ADR-001 — Modular monolith for the application backend
- **Status:** ACCEPTED
- **Context:** Two developers and a short hackathon timeline do not justify operational overhead from many independently deployed services.
- **Decision:** Use a FastAPI modular monolith with explicit domain modules and separately runnable Kafka workers.
- **Consequences:** Easier local development and integration; module boundaries must be maintained through code structure and contracts.

## ADR-002 — PostgreSQL is the commerce system of record
- **Status:** ACCEPTED
- **Context:** Price, stock, orders, reservations, and payments require transactional authority.
- **Decision:** Aiven PostgreSQL is authoritative for commerce state.
- **Consequences:** Search results and browser state must be revalidated before checkout.

## ADR-003 — OpenSearch is a derived search index
- **Status:** ACCEPTED
- **Context:** Product search must use the required OpenSearch service while preserving transactional correctness.
- **Decision:** Search queries use OpenSearch; approved catalogue data is indexed asynchronously. Checkout uses PostgreSQL.
- **Consequences:** Search may be eventually consistent; indexing must be retryable/rebuildable.

## ADR-004 — Transactional outbox for Kafka publication
- **Status:** ACCEPTED
- **Context:** A database commit followed by a separate Kafka publish can fail between the two operations.
- **Decision:** Write domain event intent to an outbox table in the same PostgreSQL transaction as the business change; publish asynchronously.
- **Consequences:** Consumers must be idempotent; publisher must retry safely.

## ADR-005 — Backend-enforced inventory reservation
- **Status:** ACCEPTED
- **Context:** Concurrent checkouts can oversell if availability is checked only in the UI or before the transaction.
- **Decision:** Reserve inventory atomically in PostgreSQL, with all-or-nothing multi-item behaviour and expiring reservations.
- **Consequences:** Requires concurrency tests, expiry handling, and idempotent reservation transitions.

## ADR-006 — AI is advisory, backend is authoritative
- **Status:** ACCEPTED
- **Context:** LLM output can be incorrect or manipulated.
- **Decision:** AI can recommend or propose; backend enforces authorization, prices, discounts, stock, payment, and order state.
- **Consequences:** AI tools must be narrow, validated, authorized, and auditable.

## Pending team decisions

- [ ] Assign integration owner.
- [ ] Confirm exact repository name and branch protection settings.
- [ ] Agree authentication approach for hackathon scope.
- [ ] Agree exact money/timestamp/API pagination conventions if existing implementation differs.
- [ ] Confirm Aiven service connection details and Kafka authentication mode.
- [ ] Decide which one or two differentiators will be attempted after P0 passes.
