# BASKET — Test Report (Phase 3 completion & final audit)

> Date: 2026-11-20 · Branch: `feature/phase-3-advanced-marketplace` (local, based on `audit/stabilisation-and-repair`)
> Machine: developer Mac (Python 3.12.14, Node 22, PostgreSQL 16 local). All results below were **executed**; nothing is extrapolated.

## Marketplace Completion — final regression (2026-11-21)

Branch `feature/marketplace-completion`, regression started 12:51 IST at `8de5111`; the only failure (formatting) was fixed in `2931e74` and re-checked. Developer Mac: Python 3.12, Node 22, PostgreSQL 16. Backend tests use the isolated `basket_db_test` database (migrated to `0034` at session start). Nothing below is extrapolated.

| Suite | Command | Result |
| :--- | :--- | :--- |
| Backend, full | `cd backend && unset DATABASE_URL && .venv/bin/python -m pytest -q -p no:cacheprovider` | **538 passed, 0 failed, 3 skipped** (173 s). Skips are opt-in live-infrastructure tests. |
| E2E API journeys A–F + role/permission suites | `pytest tests/test_mc_e2e_journeys.py tests/test_multi_role_portals.py tests/test_mc_governance.py` | **14 passed** (re-run after formatting: E2E 6 passed) |
| Feature audit (16 areas) | `scripts/audit-features.sh` | **All 16 areas passed** — auth 34, checkout isolation 23, onboarding 6, products & images 20, inventory 26, fulfilment & payments 87, governance 4, community buying 7, RFQ 3, Dukaan vs Dukaan 2, negotiator & assistant 7, price intel & sale stream 7, demand 7, OCR fallback 7, multilingual 19, Phase 2 42 |
| Migration verification | `scripts/verify-migrations.sh` | **All checks passed** — 0031–0034 up/down/re-up identical; sequential rollback to 0030 and re-apply identical; no NOT VALID constraints; all FKs indexed |
| Ruff lint | `ruff check .` | clean |
| Ruff format | `ruff format --check app tests alembic` | **failed on 1 file** (`tests/test_mc_e2e_journeys.py`) → formatted in `2931e74` → clean |
| Frontend unit tests | `npm test` | **125 / 125** (i18n coverage: en 100 %, other 11 languages 46 % of 633 keys) |
| Frontend type-check | `npm run type-check` | 0 errors |
| Frontend lint | `npm run lint` | 0 errors; 1 pre-existing `<img>` warning (`retailer/listings/new`) |
| Frontend production build | `npm run build` | ✅ 63 routes |
| Browser audit (Playwright, `basket_demo`) | manual scripted journeys | All 15 audited areas exercised; 3 defects found and fixed (see `docs/MARKETPLACE_COMPLETION.md` §2) |

Flaky-test history: `test_budget_shortfall_handling` failed once in three full runs on 2026-11-21 morning and `test_mission_recommendation_personalized_by_intent` failed in the feature audit. Both were caused by shared test-database state (see DISCREPANCY_REGISTER MC-F9), reproduced deterministically, and fixed in `f280d8e` / `ccc466d`. The final full run above has 0 failures.

Not covered by automated or browser tests: a real Razorpay hosted payment (needs test keys), a live OCR provider, multi-instance media storage.

---

## 1. Summary

| Suite | Result | Notes |
| :--- | :--- | :--- |
| Backend pytest (full) | **513 passed, 0 failed, 3 skipped** (87.7 s) | Fresh `basket_audit_test` DB migrated `0001→0030` from empty. Skips = opt-in live tests. |
| Backend live infrastructure (`tests/live`, `BASKET_LIVE_INFRA_TESTS=1`) | **1 passed, 2 skipped** | OpenSearch (Aiven) live test passed. Kafka tests skipped: broker hostname does not resolve (service powered off/deleted). |
| Ruff lint / format | clean | `ruff check app tests alembic`, `ruff format --check` |
| Alembic | upgrade empty→head ✅; downgrade `0030→0021` and re-upgrade ✅ | `alembic check`: no Phase 3 drift; pre-existing cosmetic drift only (see BACKEND_AUDIT §0.5). |
| Frontend type-check | 0 errors | `tsc --noEmit` |
| Frontend lint | 0 errors, 2 pre-existing warnings | `<img>` in retailer listing pages |
| Frontend unit tests (`node --test`) | **112 / 112** | 100 existing + 12 Phase 3 client tests |
| Frontend production build | ✅ 48 app routes (+ `/_not-found`) | 36 existing + 12 new Phase 3 routes |

Baselines: before the audit 448 backend / 100 frontend tests; after the audit 467 / 100.

## 2. Phase 3 feature tests (45 backend tests)

| Feature | Test file | Tests | Covers |
| :--- | :--- | :---: | :--- |
| 3A Demand Gap | `test_p3_demand_gap.py` | 7 | aggregation, 24 h dedupe, unique-user counting, multilingual pooling, threshold visibility, pincode scoping, fulfilment + notifications + outbox, OOS validation, zero-result search capture, guest-token inflation blocked, RBAC, admin threshold/status/trends |
| 3B Community Buying | `test_p3_community_buying.py` | 3 | join→settle→award→quote at group price→reservation→order→award USED→member PURCHASED; single use; failure; auto-settle when full; RBAC/ownership/validation; admin cancel |
| 3C Community Exchange | `test_p3_community_exchange.py` | 3 | RFQ→bids (revision)→competitor privacy→accept→quote at bid price→order; bid rules (list price, budget, ownership, index, pincode, duplicates); lifecycle & RBAC |
| 3D AI Negotiator | `test_p3_negotiator.py` | 5 | 3-round ladder, floor never breached, agree at customer price, listing floor, bundle bonus, accept→quote→order, single use, no-rule rejection, Hindi + fallback, cart-change invalidation, RBAC, rule validation |
| 3E Dukaan vs Dukaan | `test_p3_dukaan_vs_dukaan.py` | 2 | 90 s auction with competing stores on one variant, bid rules, ranking, close, award, cart switch, order at allocated price; eligibility, pincode, SSE stream, RBAC, admin |
| 3F Price Intelligence | `test_p3_price_intel_sale_stream.py` | 4 | tick on price change, day-low upsert, GENUINE_DISCOUNT, MRP_INFLATED, INSUFFICIENT_HISTORY, 404, validation |
| 3G Sale Stream | (same file) | 3 | price-drop event (≥5 %), small drops ignored, flash deal from time-limited offer, expired events never served (no Rewind) |
| 3H Bharat Multilingual | `test_p3_multilingual.py` | 6 (+7 param) | script detection & lexicon for 7 Indic languages + romanised, search via regional query, admin translations + translated-name search, preference API, RBAC |
| 3I List to Basket | `test_p3_vision_list.py` | 5 | parser (counts/sizes/x N/vernacular), 503 without provider (no fabrication), image validation (type/magic/size/base64), match→review→build cart, HTTP provider adapter (mocked transport), RBAC |
| Pipeline / jobs | `test_audit_event_pipeline.py`, `test_audit_reliability_regressions.py` | — | outbox→publisher→consumer→index with Kafka/OpenSearch doubles; Kafka outage retry; Phase 3 background jobs execute |

## 3. Regression findings during Phase 3 (fixed)

| Finding | Fix |
| :--- | :--- |
| Search used an empty in-memory mock index whenever OpenSearch was unconfigured → every dev/sandbox search returned 0 results (pre-existing) | `SearchService` uses PostgreSQL unless a cluster is configured |
| Phase 3 test fixtures in the shared `electronics` category changed Basket Mission budget outcomes | fixtures isolated in `phase3-test` category |
| Root `.env` points at live Aiven services; feature test runs synced 2 test products into the live index | removed exactly those 2 docs; `conftest.py` now blanks Kafka/OpenSearch unless `BASKET_LIVE_INFRA_TESTS=1` |
| Demand unique-shopper count inflatable with rotating guest tokens | unique counts only for authenticated customers; retailers/admins cannot cast signals |
| Expression unique indexes missing from models (autogenerate would drop them) | declared on models |
| Phase 1 test fulfilled an unpaid order (blocked by audit rule) | test marks order paid first |

## 4. Razorpay regression

All payment tests in `test_payments.py`, `test_orders*.py` pass (initiation idempotency, signature verification, server fetch/capture, webhooks incl. HMAC/dedupe/leases, partial captures, refunds incl. admin/internal-only access, reconciliation, SLA). Phase 3 prices reach Razorpay only through the server-side quote/order totals. **No live Razorpay sandbox call was made** (mocks only, as required).

## 5. Integrated journeys (API level, automated)

* Customer: register → address → cart → quote → reservation → order → payment initiate/verify (mocked gateway) — `test_payments.py`.
* Customer Phase 3: group buy, RFQ, negotiation and auction each end in a real order at the special price (tests above).
* Retailer: listing price change → price history + `price.changed` + Sale Stream; demand fulfil; RFQ/auction bids; group-buy creation; negotiation rules.
* Admin: demand thresholds/status/trends, group-buy monitoring/cancel, RFQ/auction monitoring, translations, fulfilment/returns/refunds (audit).

Browser-driven end-to-end UI journeys were **not** executed (no Playwright/Cypress suite exists in the repo); UI pages were verified by type-check, lint and production build.

## 6. Live vs mocked

| Service | Status |
| :--- | :--- |
| PostgreSQL 16 (local) | **Live** — all suites |
| OpenSearch (Aiven) | **Live** — isolated probe index: projection, external-version conflict, regression for lower aggregate counters, search, delete, cleanup |
| Kafka (Aiven) | **Unavailable** — DNS for the bootstrap host fails. Producer/consumer/outbox verified with in-memory doubles only. |
| Razorpay | Mocked (by instruction) |
| OCR / vision provider | Not configured — adapter tested with a mocked transport; endpoint returns 503 `OCR_PROVIDER_UNAVAILABLE` |
