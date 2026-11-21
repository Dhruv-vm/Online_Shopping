# BASKET — Version 2.0 Implementation Plan

> Branch: `feature/version-2-development` (from `integration` @ `d38d6e3`, contains `v1.0` = `d517b1a`)
> Companion to [`VERSION_2_FEATURE_ROADMAP.md`](VERSION_2_FEATURE_ROADMAP.md); evidence in [`VERSION_1_FUNCTIONAL_AUDIT.md`](VERSION_1_FUNCTIONAL_AUDIT.md).
> **Status: plan only. No implementation starts until approved.** Each phase below ends with a stop for review.

---

## 0. Ground rules for every change

1. **No UI/UX change.** No layout, colour, font, spacing, branding, navigation, animation or CSS edits. Frontend edits are limited to request payloads, headers, `t()` string lookups and error handling, and must leave the rendered page pixel-identical in English.
2. **v1.0 is frozen.** The `v1.0` tag and `d517b1a` are never moved or rewritten. All work is new commits on `feature/version-2-development`.
3. **No push, PR, merge or deploy** from this workstream.
4. **Databases.** `basket_db` is never reset or migrated destructively. Verification runs on `basket_db_test`, throwaway `*_verify` databases and isolated `*_demo` databases built with `scripts/reset-demo-db.sh`.
5. **Secrets** stay in `.env` (gitignored) and never appear in code, docs, logs or commits.
6. **Integrations are reported as they are.** Anything not verified against the real provider is labelled "not verified".
7. **Small commits**, one roadmap item per commit (or a few), each with tests.

## 1. Definition of done (per item)

An item is complete only when every gate below passes:
- [ ] Unit/integration tests added for every case listed under the item's "Tests" in the roadmap.
- [ ] `ruff check` + `ruff format --check` clean; full backend suite green.
- [ ] Frontend `test`, `type-check`, `lint`, `build` green (where frontend is touched), and an English screenshot comparison shows no visual change.
- [ ] `scripts/audit-features.sh` green; `scripts/verify-migrations.sh` green if a migration is added (with a working downgrade).
- [ ] Live re-run of the relevant `v1audit_probe` checks on a fresh `*_demo` database shows the defect fixed.
- [ ] Docs updated (`DISCREPANCY_REGISTER.md`, feature tracker) with the evidence.

## 2. Phases

### Phase A — P0 correctness (no product decisions needed) · ≈2 days
| Step | Item | Files | Migration | Frontend |
| --- | --- | --- | :---: | --- |
| A1 | **P0-1** auction-accept crash | `cart/integration.py`; tests in `tests/test_auctions*.py`, `test_exchange*.py` | — | — |
| A2 | **P0-3** payment-initiation idempotency | `payments/router.py`, `payments/service.py`; `components/checkout/razorpay-modal.tsx` (pass key only) | — | logic only |
| A3 | **P0-4** search engine fallback when the index can't be kept in sync | `search/service.py`, `governance` health | — | — |

**A1 detail**
1. In `set_customer_cart_lines`, compute `keep = {line.listing_id for line in lines}`, delete only `remove_listing_ids - keep`, and update the quantity of existing items in `keep`.
2. Wrap the accept flush so any residual `IntegrityError` becomes 409 `CART_CONFLICT`.
3. Regression tests:
   - same-listing winner;
   - different-listing winner;
   - RFQ accept with an overlapping listing;
   - List to Basket adding a listing already in the basket.
4. Live: probe check "auction accept" returns 200, and the order total equals the winning bid.

**A2 detail**
1. Router: when the header is absent, pass `idempotency_key=None`.
2. Service: with no key, look up the latest attempt for the order with status `PENDING`, the same amount, and an unexpired window. If one exists, return it; otherwise create a new one.
3. Use `SELECT … FOR UPDATE` on the order row so concurrent initiations serialise.
4. Frontend: generate a key once per modal open, `crypto.randomUUID()` stored in a ref, and send it as `Idempotency-Key`. A retry inside the same modal reuses it.
5. Tests:
   - repeat without a key → 1 attempt;
   - repeat with the same key → replay;
   - after `FAILED` → a new attempt;
   - 5 concurrent calls → 1 attempt.

**A3 detail:** in `search/service.py`, choose OpenSearch only when it's configured **and** the outbox dispatcher is healthy (Kafka reachable, or the P1-2 direct dispatcher is enabled). Otherwise use PostgreSQL and report `engine=postgres_fallback` with a reason in system health.

➡ **Stop for review.**

### Phase B — P0 discounts (needs decisions) · ≈2 days
Decisions required before starting:
1. **Stacking policy.** Proposed: best single platform deal + retailer listing offer.
2. **Code entry.** Approve a checkout code input (UI addition), or ship backend-only so coded deals are non-redeemable until the UI is approved.

| Step | Work |
| --- | --- |
| B1 | Add optional `discount_code` to the quote request; filter coded deals by exact (case-insensitive) match; reject an unknown/expired code with 422 `INVALID_DISCOUNT_CODE`. |
| B2 | Apply the stacking policy in `calculate_unit_discount` / `quote_service`; expose the applied discount IDs on the quote. |
| B3 | Check `min_order_paise` against the basket subtotal (before tax and delivery). |
| B4 | Increment usage at order creation and release it on pre-payment cancellation/expiry; enforce `usage_limit` under a row lock. |
| B5 | Frontend (only if approved): send `discount_code` from the existing checkout form state. |

Tests: as listed under P0-2, plus re-running the 8 seeded demo discounts against expected totals.

➡ **Stop for review.**

### Phase C — Payments verification and infrastructure reliability · ≈5 days
| Step | Item | Notes |
| --- | --- | --- |
| C1 | **P1-1** Razorpay sandbox runbook | Requires a webhook secret and a tunnel URL from you. Test cards/UPI only. Output: `docs/RAZORPAY_SANDBOX_VERIFICATION.md` with provider IDs. |
| C2 | **P1-2** outbox direct dispatcher | Behind a `OUTBOX_DISPATCH=direct|kafka` setting; default `kafka` if `KAFKA_BOOTSTRAP_SERVERS` resolves, else `direct`. Handlers reused from the existing consumers. Also add a per-database index prefix (MC-12) so environments never share an index. |
| C3 | **P1-3** advisory locks + `SKIP LOCKED` on periodic jobs | One lock key per job name. |
| C4 | **P1-9** `SQL_ECHO` flag + one structured log line per job run | Default off. |

➡ **Stop for review.**

### Phase D — Functional completion · ≈8–10 days
| Step | Item | Notes |
| --- | --- | --- |
| D1 | **P1-5** translation coverage | Page by page, in order: cart → checkout → orders → account → retailer → admin. Each page commit includes an English screenshot diff (must be identical) and a coverage report. Dictionaries filled for 11 languages, marked `needs_native_review`. Category/product content translations seeded. Lexicon expanded. |
| D2 | **P1-4** retailer notifications | Only after product approval of the event list. |
| D3 | **P1-8** test-database isolation | |

➡ **Stop for review.**

### Phase E — Provider integrations (each needs explicit approval and credentials)
| Step | Item | Prerequisite |
| --- | --- | --- |
| E1 | **P1-6** OCR provider | Provider chosen, account and key in `.env`, sample images |
| E2 | **P1-7** LLM negotiator assistant | Provider chosen, cost cap, data policy; the rule engine remains the price authority |

Each integration ships a recorded-response test suite and a live verification note. Until verified live, it is labelled "configured, not verified".

### Phase F — P2 (scheduled after Phases A–D)
P2-1 object storage, P2-2 abuse limits, P2-3 price-history snapshots, P2-4 returns/refunds in the sandbox, P2-5 performance pass. P2-6 (group-buy commit-to-pay) is a new feature and is not started without a product decision.

## 3. Database changes summary

| Item | Change | Migration | Destructive? |
| --- | --- | :---: | :---: |
| P0-1, P0-3, P0-4 | none | — | — |
| P0-2 | optional index on `discounts(code)` | 0035 | no |
| P1-4 | possibly a recipient column on notifications | 0036 (if needed) | no (additive) |
| P1-5 | translation rows (data) | data seed script | no |
| P1-7 | optional `model` column on negotiation messages | additive | no |
| P2-3 | none (unique key exists) | — | — |
| P2-5 | indexes as measured | additive | no |

All migrations are additive, verified with `scripts/verify-migrations.sh` (up, down, re-up) on a throwaway database, and never run against `basket_db` by this workstream.

## 4. Risks

| Risk | Mitigation |
| --- | --- |
| Discount policy change alters totals customers have seen | Applies only to new quotes; existing orders keep their stored totals |
| Direct dispatcher double-processes with Kafka later enabled | A single setting selects one dispatcher; handlers are idempotent on event ID |
| Translation work drifts into visual change | Per-page English screenshot diff is a merge gate |
| Provider costs (OCR/LLM/Razorpay) | Sandbox/test keys only; cost cap and approval before any live key |
| Shared test DB flakiness until P1-8 | Run full suites twice when a failure looks order-dependent |

## 5. Approvals requested

1. Start **Phase A** (P0-1, P0-3, P0-4). It needs no product decisions; the only frontend change adds an idempotency header, with no visual change.
2. **Discount stacking policy** and whether a **code input** may be added to checkout (Phase B).
3. **Kafka vs direct dispatcher** (C2), and a Razorpay webhook secret plus tunnel for C1.
4. The retailer notification event list (D2).
5. OCR and LLM providers (Phase E), when you want them.
