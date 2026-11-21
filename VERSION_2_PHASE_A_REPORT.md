# BASKET — Version 2.0 Phase A Report (P0 correctness)

> Scope: roadmap items **P0-1, P0-3, P0-4** (implementation plan steps A1, A2, A3). Phase B (discounts) and later phases were **not** started.
> Branch: `feature/version-2-development` · Starting commit: `4d7ada9` · Code commits: `dfed80a`, `bf6919e`, `654343c` (§9).
> `v1.0` tag unchanged (`68ac8ff…` → `d517b1a`). Nothing pushed, merged, deployed or opened as a PR.

---

## 1. Summary

| Step | Defect (v1.0 audit) | Result | Verification level |
| --- | --- | --- | --- |
| A1 | D1: accepting a Dukaan vs Dukaan bid returned **500** when the winning listing was already in the basket | **Fixed** | Automated tests + live API/DB probe |
| A2 | D4: every "Pay" press without an `Idempotency-Key` created a **new Razorpay order** | **Fixed** (backend + frontend key) | Automated tests + live probe against **Razorpay test mode** (order creation only) |
| A3 | D5: search could read a **stale/foreign OpenSearch index** while Kafka/outbox delivery is down | **Fixed** (PostgreSQL fallback + health reporting) | Automated tests + live probe with the real `.env` (OpenSearch configured, Kafka unreachable) |

## 2. Root causes and fixes

### A1 — Dukaan vs Dukaan acceptance crash
- **Root cause.** `set_customer_cart_lines` (`backend/app/modules/cart/integration.py`) deleted the basket's original line and inserted the winning line. When both were the **same listing** (the basket's own store wins, the normal case), SQLAlchemy's unit of work flushed the INSERT before the DELETE, violating the unique index `uq_cart_listing`. The request failed with an unhandled `IntegrityError` and the auction could never be accepted.
- **A second path found during the fix.** The same helper inserted twice when a listing appeared twice in `lines` (List to Basket with a repeated item). That also produced a 500.
- **Fix (minimal, same file):**
  - Compute `keep = {listing ids in lines}`, delete only `remove_listing_ids − keep`, and update existing lines in place.
  - Track newly added items so a repeated listing updates rather than re-inserts (last quantity wins, matching how existing lines were already treated).
  - Convert any residual `uq_cart_listing` violation (e.g. a concurrent request) into **409 `CART_CONFLICT`**. Other integrity errors are re-raised unchanged.
- Callers `auctions/service.py`, `exchange/service.py` (RFQ) and `vision/service.py` (List to Basket) are unchanged and benefit automatically.

### A2 — Payment initiation idempotency
- **Root cause.** `POST /orders/{id}/payments` replaced a missing `Idempotency-Key` with a fresh `uuid4()`, and the checkout button never sent a key. Every press created a new attempt and a new Razorpay order.
- **Backend fix:**
  - **Router** (`payments/router.py`): no longer invents a key.
  - **Service** (`payments/service.py`): new `_reusable_keyless_attempt`. Without a key, it reuses the order's latest **PENDING** attempt with the same amount and currency (inside the existing unexpired-payment-window check). If another request is still `CREATING`, it waits for that request (same bounded wait as the keyed path), then **re-takes the order row lock** before re-checking, so a new attempt is never created unlocked. `CREATION_AMBIGUOUS` still returns the existing ambiguity error. Only when nothing is reusable does it create an attempt, with an internal `auto-<uuid>` key.
  - Concurrency is serialised by the order row lock already taken at the start of `initiate_payment` (`SELECT … FOR UPDATE`).
  - Requests with an explicit key behave exactly as in v1.0.
- **Frontend fix (logic only):**
  - New `frontend/lib/payments/idempotency.ts` keeps **one key per order** while the checkout page is open. The key is reused on every retry and changes only for a different order.
  - If the API answers `PAYMENT_ATTEMPT_FAILED` (that key's attempt failed permanently), it rotates to a new key once and retries.
  - `razorpay-modal.tsx` now passes the key. No markup, text, class or style changes.
- **Unchanged:** signature validation, replay with the same key, the `FAILED`-key rejection, reservation expiry, second-capture auto-refund and SLA escalation (the 37 existing payment tests pass).

### A3 — Safe search fallback
- **Root cause.** The OpenSearch index is updated only through outbox → Kafka → `OpenSearchConsumer`. With Kafka unreachable, nothing updates the index, yet `SearchService` queried it whenever `OPENSEARCH_URL` was set.
- **Fix:**
  - New `backend/app/core/search/index_health.py` decides the engine:
    | Condition | Engine | Reason |
    | --- | --- | --- |
    | OpenSearch not configured | `postgres` | `OPENSEARCH_NOT_CONFIGURED` |
    | Kafka not configured | `postgres_fallback` | `KAFKA_NOT_CONFIGURED` |
    | Outbox publisher not connected | `postgres_fallback` | `OUTBOX_PUBLISHER_NOT_CONNECTED` |
    | Indexing consumer not running | `postgres_fallback` | `SEARCH_INDEXER_NOT_RUNNING` |
    | Oldest PENDING outbox event older than `SEARCH_INDEX_MAX_LAG_SECONDS` (default 300 s) | `postgres_fallback` | `OUTBOX_BACKLOG` |
    | All healthy | `opensearch` | — |
  - The background supervisor registers the publisher, and the app lifespan registers the indexer. The result is cached for 10 s on the search path.
  - `SearchService` (search **and** suggestions) never queries an untrusted index. The response carries the new optional field `engine_reason`.
  - Health:
    - `GET /ready` → `checks.search = {engine, reason, detail}`.
    - `GET /api/v1/admin/system/health` → new `search_engine` field. The existing **OpenSearch** row now reports `degraded` with the fallback reason instead of always "Configured". It is the same row, so no layout change.
  - No direct outbox dispatcher was added (that is Phase C, P1-2).

## 3. Files changed

| File | Change |
| --- | --- |
| `backend/app/modules/cart/integration.py` | A1 fix + 409 `CART_CONFLICT` |
| `backend/app/modules/payments/router.py` | A2: pass the absent key through |
| `backend/app/modules/payments/service.py` | A2: keyless reuse of the PENDING attempt under the order lock |
| `backend/app/core/search/index_health.py` *(new)* | A3: engine decision + process state |
| `backend/app/modules/search/service.py` | A3: gate OpenSearch (search + suggestions), `engine_reason` |
| `backend/app/modules/search/schemas.py` | A3: optional `engine_reason` |
| `backend/app/core/config.py` | A3: `SEARCH_INDEX_MAX_LAG_SECONDS` (default 300) |
| `backend/app/core/background.py` | A3: register/unregister the outbox publisher |
| `backend/app/main.py` | A3: register the indexer; `/ready` search check |
| `backend/app/modules/governance/router.py` | A3: truthful OpenSearch row + `search_engine` |
| `frontend/lib/payments/idempotency.ts` *(new)* | A2: per-order key |
| `frontend/components/checkout/razorpay-modal.tsx` | A2: send the key; rotate only after `PAYMENT_ATTEMPT_FAILED` |
| `frontend/package.json` | Add the new unit test to `npm test` |
| `backend/tests/test_v2_phase_a_cart_lines.py` *(new)* | 5 tests |
| `backend/tests/test_v2_phase_a_payment_idempotency.py` *(new)* | 5 tests |
| `backend/tests/test_v2_phase_a_search_fallback.py` *(new)* | 6 tests |
| `frontend/lib/payments/idempotency.test.ts` *(new)* | 4 tests |

No migrations. No new dependencies.

## 4. Tests added

**A1 (`test_v2_phase_a_cart_lines.py`)**
1. Winning listing already in the basket → accept 200, the listing appears once, the quote line is at the bid price, and the order total equals the quote.
2. A different store wins → the original line is replaced, and an item added after the auction started is preserved.
3. RFQ accept for a listing already in the basket → one line, quantity from the bid, award price applied.
4. List to Basket with a listing already in the basket, plus the same new listing twice → 200, one row each.
5. Residual unique violation → `AppException` 409 `CART_CONFLICT`.

**A2 (`test_v2_phase_a_payment_idempotency.py`)**
1. Three keyless initiations → one attempt, one provider order.
2. Same key twice, then keyless → all the same attempt.
3. After the attempt is `FAILED` → a new attempt (`attempt_number` + 1).
4. **Five concurrent** keyless initiations → one attempt, one provider order.
5. Distinct explicit keys → still a deliberate new attempt (v1.0 behaviour kept).

**A3 (`test_v2_phase_a_search_fallback.py`)**
1. The engine decision for each pipeline state.
2. An outbox backlog → `OUTBOX_BACKLOG`.
3. An untrusted index is never queried (search + suggestions).
4. A trusted index is used.
5. Default wiring with OpenSearch configured and no Kafka → fallback, client never called.
6. Admin system health and `/ready` report engine and reason.

**Frontend (`idempotency.test.ts`)**
1. The same order keeps its key.
2. A different order gets a new key.
3. Keys are unique and ≤ 128 characters.
4. Only `PAYMENT_ATTEMPT_FAILED` rotates the key.

**Proof that the tests catch the defects.** Run against the unmodified v1.0 code, the new tests fail:
- A1: the auction and List to Basket cases fail with `IntegrityError … uq_cart_listing`, and the 409 case fails.
- A2: the keyless, same-key-then-keyless, and five-concurrent cases fail.

With the fixes, all pass.

## 5. Test results (run on 2026-11-21, after all changes)

| Check | Result |
| --- | --- |
| `ruff check` / `ruff format --check` | clean / 278 files formatted |
| Backend full suite | **554 passed, 0 failed, 3 skipped** (v1.0: 538 passed; +16 new). The 3 skips are opt-in live-infrastructure tests, unchanged |
| E2E journeys + role/permission suites | 14 / 14 |
| `scripts/audit-features.sh` (16 areas) | all passed |
| `scripts/verify-migrations.sh` | ALL MIGRATION CHECKS PASSED (no migration added; head `0034`) |
| Frontend `npm test` | **129 / 129** (v1.0: 125; +4) |
| Frontend type-check / lint / build | 0 errors / 0 errors (1 pre-existing `<img>` warning) / 63 routes |

**Live probe** (`backups/mc/v2a_probe.py`, results in `backups/mc/v2a_probe_results.json`). It ran on a fresh isolated `basket_v2a_demo` built with `scripts/reset-demo-db.sh`. The API ran from this working tree with the real `.env` (OpenSearch configured, Kafka unreachable, Razorpay **test mode**).

| Check | Result | Evidence |
| --- | --- | --- |
| A1 | **PASS** | Basket's own store (retailer 3) bid ₹1,00,134.99 against a list price of ₹1,00,734.99. After 90 s: accept **200 AWARDED**; basket has 1 line (1 DB row); order 201; order total = quote total. No `IntegrityError` or traceback in the API log. |
| A2 | **PASS** | 3 keyless initiations → **1** Razorpay sandbox order. The same explicit key twice → same order. DB: 2 attempts (1 keyless + 1 keyed with a different key, as designed). Orders cancelled afterwards to release stock. |
| A3 | **PASS** | `/search?q=laptop` → `engine=postgres_fallback`, `engine_reason=OUTBOX_PUBLISHER_NOT_CONNECTED`, 1 result. Admin health `search_engine` and `/ready` report the same. The OpenSearch row shows `degraded`. The shared OpenSearch cluster was **not** queried for search. |

Note on A1 pricing (existing v1.0 behaviour, not changed): an award only replaces the price when it is **lower** than the normal discounted price (`quote_service.py`, best price for the customer). In the probe the MacBook already had a seeded 12 % deal (₹88,646.79), so the customer paid that rather than the higher bid. Relevant to Phase B's discount policy.

## 6. UI/UX impact

**None.**
- The frontend diff is limited to an import, a `useRef`, and the initiate call in `razorpay-modal.tsx`, plus a new non-visual module and a `package.json` test-script entry.
- No JSX, text, `className`, style, CSS, layout, branding, navigation or loader changes. The rendered output is unchanged by construction, so no screenshot comparison was required.
- The admin settings page shows the same rows. Only the data in the OpenSearch row's status and detail is now truthful, and only when OpenSearch is configured.

## 7. Database and security impact

- **Database:**
  - No schema change and no migration.
  - `basket_db` was not touched.
  - Tests used `basket_db_test`; the live probe used the new isolated `basket_v2a_demo`. Both `*_demo` databases from the audits remain and are isolated.
  - One test inserts and then deletes its own outbox row.
- **Security:**
  - Ownership, role checks (`ensure_can_shop`), signature validation, replay protection and the FAILED-key rejection are unchanged.
  - Keyless reuse is scoped to the order the caller already proved ownership of, and only while the payment window is open.
  - No secrets in code, tests, logs or docs.

## 8. Remaining risks and unverified integrations

- **Not verified:**
  - Completing a payment in Razorpay's hosted window.
  - Live webhooks.
  - Sandbox refunds.
  These remain for P1-1 / Phase C. Only sandbox order creation was exercised.
- **Explicit distinct keys** still create a new attempt each (v1.0 semantics). The checkout page uses one key per order per page load, so reloading the page and paying again creates a second attempt. Any double capture is still handled by the existing auto-refund.
- **A3 is per process.** Publisher and indexer state are tracked inside the API process (the current deployment model). With separately deployed consumers, `SEARCH_INDEXER_NOT_RUNNING` would wrongly force the fallback, which is safe but conservative. The outbox-backlog rule works across processes.
- **Foreign index (MC-12).** A3 stops search from reading the shared index while this environment's pipeline is down. A per-database index prefix is still needed before two environments share one cluster with healthy pipelines (P1-2).
- **Shared test database (MC-04).** It is still persistent. The A3 "healthy" test avoids leftover outbox rows by using a large lag limit.

## 9. Commits (local only, author Dhruv-vm)

| Commit | Content |
| --- | --- |
| `dfed80a` | fix(cart): A1 + tests |
| `bf6919e` | fix(payments): A2 backend + frontend key + tests |
| `654343c` | fix(search): A3 + tests |
| *(this report)* | docs: Phase A report + discrepancy register entries |

Process note: at 14:03 IST, during this phase, the working copy was checked out at `v1.0` (detached) by something outside this session. No commit was made there. With your approval the branch was switched back to `feature/version-2-development` (the working-tree changes carried over without conflict) before committing. The full regression ran on identical code, because the branch differs from `v1.0` only by the three planning documents.

**Phase A is complete. Phase B (discounts) is not started and needs your decisions on the stacking policy and on a checkout code input.**
