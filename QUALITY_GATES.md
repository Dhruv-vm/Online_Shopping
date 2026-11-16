# BASKET — Quality Gates and Definition of Done

Quality is the release criterion. A feature is not complete because a page renders or an endpoint returns HTTP 200.

## 1. Foundation gate

- [ ] New developer can follow README setup without undocumented steps.
- [ ] Frontend starts and backend starts independently.
- [ ] Environment configuration is validated at startup.
- [ ] `.env.example` contains placeholders, not real secrets.
- [ ] PostgreSQL connection and Alembic migration work.
- [ ] Health and readiness endpoints behave correctly.
- [ ] Lint, formatting, type checks, and baseline tests pass.

## 2. Feature gate

Every feature must have:
- [ ] Clear user/business outcome.
- [ ] Agreed API and data contract.
- [ ] Authorization and input validation.
- [ ] Loading, empty, success, and error states where relevant.
- [ ] Tests for happy path and important failure paths.
- [ ] Logs that help diagnose failures without exposing secrets.
- [ ] Documentation sufficient for another developer to operate it.
- [ ] No dead buttons, fake success, or misleading demo claims.

## 3. Commerce gate

- [ ] Product and variant identity is stable.
- [ ] Price and stock are revalidated server-side.
- [ ] Cart quantity and availability constraints are enforced.
- [ ] Checkout is idempotent.
- [ ] Multi-item reservation is all-or-nothing.
- [ ] Concurrent checkout cannot oversell.
- [ ] Payment status is verified server-side.
- [ ] Order history is persisted and retrievable.
- [ ] Order item snapshots preserve purchase-time details.

## 4. Infrastructure proof gate

### PostgreSQL
- [ ] Core records are persisted and can be queried.
- [ ] Constraints and transactions protect critical invariants.

### OpenSearch
- [ ] Search endpoint actually queries OpenSearch.
- [ ] Approved product data is indexed.
- [ ] Indexing failures can retry or be rebuilt.
- [ ] Checkout never trusts search index price/stock.

### Kafka
- [ ] An order transaction writes an outbox event.
- [ ] Publisher sends it to Kafka.
- [ ] A consumer receives and processes it.
- [ ] Duplicate delivery does not duplicate side effects.
- [ ] Failure/retry behaviour is documented.

## 5. Security gate

- [ ] No secrets committed.
- [ ] Role checks are server-side.
- [ ] Payment callbacks are verified.
- [ ] Uploads have size/type/content validation if enabled.
- [ ] No arbitrary SQL or unrestricted tools exposed to AI.
- [ ] Logs do not expose tokens, passwords, payment secrets, or private data.

## 6. Demo gate

- [ ] Demo path is repeatable from a clean state.
- [ ] Seed data is deterministic.
- [ ] External dependencies and sandbox limitations are disclosed.
- [ ] Network/service failure has a graceful and honest UI.
- [ ] Screenshots/video backup exists.
- [ ] A developer can explain the architecture and show real service activity.

## 7. Release rule

A P0 failure blocks release. Optional features cannot compensate for a broken core journey or fake infrastructure integration.

Do not lower a gate to make a feature appear complete. Reduce scope instead.
