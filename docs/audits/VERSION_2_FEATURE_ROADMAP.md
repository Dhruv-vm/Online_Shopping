# BASKET — Version 2.0 Functional Roadmap

> Baseline: `v1.0` (`d517b1a`) · Development branch: `feature/version-2-development` (from `integration` @ `d38d6e3`)
> Evidence: [`VERSION_1_FUNCTIONAL_AUDIT.md`](VERSION_1_FUNCTIONAL_AUDIT.md) · Execution detail: [`VERSION_2_IMPLEMENTATION_PLAN.md`](VERSION_2_IMPLEMENTATION_PLAN.md)
> **Scope rule:** functional, backend and integration work only. No UI/UX, layout, styling, branding or navigation changes. Frontend files are touched only where a functional fix requires it, preserving appearance exactly.
> **Status: proposal — nothing below is implemented. Awaiting approval.**

---

## Summary

| ID | Priority | Item | Area | Complexity | Decision needed |
| --- | :---: | --- | --- | :---: | --- |
| P0-1 | P0 | Dukaan vs Dukaan acceptance crash | H | S | — |
| P0-2 | P0 | Discount codes, stacking and minimum-order rules | A | M | **Yes — stacking policy, code entry** |
| P0-3 | P0 | Duplicate Razorpay orders on repeated "Pay" | B | S | — |
| P0-4 | P0 | Search reads a stale/foreign index while Kafka is down | Infra | S (config) + M | Yes — demo search engine |
| P1-1 | P1 | Razorpay sandbox end-to-end verification (success, failure, cancel, webhook, refund, reconciliation) | B | M | Needs public webhook URL |
| P1-2 | P1 | Outbox delivery without Kafka (search-index sync and projections) | Infra / A | M | Yes — provision Kafka or DB dispatcher |
| P1-3 | P1 | Concurrency-safe periodic jobs | A | S | — |
| P1-4 | P1 | Retailer notifications for RFQs, auctions and orders | H | S–M | Yes — new notification type (product decision) |
| P1-5 | P1 | Functional translation coverage (UI strings, error messages, catalogue content, search lexicon) | E | L | — |
| P1-6 | P1 | OCR provider integration for List to Basket | D | M | Yes — provider choice, cost |
| P1-7 | P1 | LLM-assisted negotiator with rule-engine guardrails | C | M | Yes — provider choice, cost, data policy |
| P1-8 | P1 | Test-database isolation | Quality | M | — |
| P1-9 | P1 | Logging hygiene (SQL echo, structured job logs) | Infra | S | — |
| P2-1 | P2 | S3-compatible object storage for media | Infra | M | Yes — storage provider |
| P2-2 | P2 | Abuse limits on RFQ / auction / demand creation | H, I | S | Yes — limits |
| P2-3 | P2 | Price-history integrity (daily tick guarantee, gap reporting) | F | S | — |
| P2-4 | P2 | Returns and refunds end-to-end in sandbox (customer → admin → Razorpay) | B | M | — |
| P2-5 | P2 | API performance pass (query counts, indexes on hot paths) | Infra | M | — |
| P2-6 | P2 | Group-buy payment option (commit-to-pay) | G | L | **Yes — new feature** |

Already implemented in v1.0 and **not** proposed again:
- payment signature validation and replay with the same idempotency key;
- second-capture auto-refund;
- reservation expiry;
- the negotiator's floor and round limits;
- demand de-duplication;
- price alerts with in-app notification;
- group-buy settlement via price awards;
- RFQ above-list bid rejection;
- auction above-list bid rejection;
- admin audit reasons.

---

## P0 — Critical defects and demo blockers

### P0-1 · Dukaan vs Dukaan acceptance crash
1. **Existing status:** start, live bidding and closing work; acceptance fails with HTTP 500.
2. **Problem:** `set_customer_cart_lines` deletes the basket's original line and inserts the winning line. When it is the **same listing**, which is normal when the basket's own store wins, SQLAlchemy flushes the INSERT before the DELETE and violates `uq_cart_listing`. The transaction rolls back, so the auction can never be accepted. Reproduced twice live. The existing test uses a different winning listing, so it passes.
3. **Solution:** in `set_customer_cart_lines`, never delete a listing that is also in `lines`; update its quantity in place. Convert any remaining `IntegrityError` into a 409 instead of a 500.
4. **Backend:** `cart/integration.py` (≈5 lines). Same helper used by RFQ and List to Basket — they benefit too.
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** none.
8. **Tests:**
   - winner sells the same listing already in the basket → 200, basket at bid price via award;
   - winner sells a different listing → old line removed;
   - same for RFQ accept with an overlapping listing;
   - the quote total equals the winning bid.
9. **Acceptance:** auction accept returns 200 in both cases; the quote total equals the winning bid; no 500s in the API log.
10. **Complexity:** S (½ day).

### P0-2 · Discount codes, stacking and minimum-order rules
1. **Existing status:** admin deals and retailer offers are stored in basis points and applied at quote time.
2. **Problems (verified):**
   - (a) a deal's `code` is never checked, so coded deals apply to every customer;
   - (b) all matching platform deals **stack** (two 7 % deals = 14 % off);
   - (c) `min_order_paise` is compared with the unit price;
   - (d) `times_used` / `usage_limit` — usage is not incremented on order placement *(to confirm during implementation)*.
3. **Solution:**
   - Automatic deals (no code) apply as today.
   - Coded deals apply only when the customer supplies a matching code on the quote request (`discount_code`, optional).
   - Stacking: **proposed** — at most one platform deal (the best for the customer) plus the retailer's own offer.
   - Minimum order is checked against the basket subtotal.
   - Usage is incremented when the order is created and released if it's cancelled before payment.
4. **Backend:** `pricing/discount_service.py`, `quote_service.py`, the quote request schema, and order creation/cancellation hooks.
5. **Frontend (functional only):** to let customers redeem a code, the checkout must send `discount_code`. That needs an input field, which is a UI addition → **requires your approval**. Without it, coded deals are simply not redeemable (safer than today).
6. **Database:** none (fields exist). Optionally index `discounts(code)`.
7. **Dependencies:** your stacking-policy decision.
8. **Tests:**
   - coded deal not applied without the code, applied with it;
   - wrong code → 422 `INVALID_DISCOUNT_CODE`;
   - two auto deals → only the best one applied;
   - retailer offer + platform deal → both applied;
   - minimum order checked against the subtotal;
   - usage limit enforced across orders.
9. **Acceptance:** the quote's discount equals the policy for every scenario above; existing discount tests still pass.
10. **Complexity:** M (2 days).

### P0-3 · Duplicate Razorpay orders on repeated "Pay"
1. **Existing status:** with an `Idempotency-Key` the endpoint replays correctly. Without one, the router invents a key.
2. **Problem:** the checkout page sends no key, so every click or retry creates a new payment attempt and Razorpay order (2 attempts verified for one order). A double capture is auto-refunded, but customers can be charged twice and then refunded.
3. **Solution:**
   - **Backend:** when no key is sent, reuse the order's active `PENDING` attempt if the amount is unchanged and the payment window is open.
   - **Frontend:** send a stable key per order (e.g. `order:<id>:<attempt>` kept in memory/sessionStorage). This is a logic change only, with no visual change.
4. **Backend:** `payments/router.py`, `payments/service.py`.
5. **Frontend:** `components/checkout/razorpay-modal.tsx` (pass the key; no markup change).
6. **Database:** none.
7. **Dependencies:** none.
8. **Tests:**
   - two initiations without a key → same provider order, 1 attempt row;
   - after the first attempt FAILED → a new attempt is allowed;
   - after the window expires → 409;
   - concurrent initiations → one attempt.
9. **Acceptance:** at most one `PENDING` attempt per order at any time; repeated "Pay" clicks show the same Razorpay order.
10. **Complexity:** S (½–1 day).

### P0-4 · Search reads a stale or foreign index while Kafka is down
1. **Existing status:** OpenSearch is updated only by a Kafka consumer. Kafka is unreachable, so the outbox never drains (83 events PENDING since 2026-11-20). The root `.env` enables OpenSearch.
2. **Problem:** `/search` (and List to Basket, which uses it) can return products that are out of date or belong to another database. This was observed in the release audit, and v1.0 was mitigated in code for List to Basket only.
3. **Solution:**
   - **Immediate, config only:** run demos with `OPENSEARCH_URL=""` (PostgreSQL search is accurate).
   - **Code:** at startup, if OpenSearch is configured but Kafka is not reachable, log a degraded state and route search to PostgreSQL until the index is in sync, then expose that in system health. The full fix is P1-2.
4. **Backend:** `search/service.py` (engine selection), `governance/router.py` (health detail).
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** a P1-2 decision for the permanent fix.
8. **Tests:**
   - OpenSearch configured + Kafka down → search engine `postgres_fallback`;
   - health shows the reason;
   - when both are up → `opensearch`.
9. **Acceptance:** search results always match the database the API is connected to.
10. **Complexity:** S (config) + M (code, 1 day).

---

## P1 — Feature completion and integration

### P1-1 · Razorpay sandbox end-to-end verification
1. **Status:** sandbox order creation verified live; signature checks, replay, capture and auto-refund are covered by automated tests with mocked provider calls.
2. **Problem:** not yet verified against Razorpay's sandbox:
   - a completed payment in the hosted checkout;
   - a payment failure;
   - a cancellation (closing the window);
   - delivered webhooks;
   - a refund;
   - reconciliation of an ambiguous attempt.
3. **Solution:** a scripted sandbox runbook plus a small verification harness:
   - Razorpay test cards and UPI test IDs;
   - a tunnel for webhooks (`cloudflared`/`ngrok`);
   - set `RAZORPAY_WEBHOOK_SECRET`;
   - record order, payment and refund states after each step.
   Fix any defects found.
4. **Backend:** none expected; fixes only if defects are found.
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** test keys (present), a webhook secret and a public URL.
8. **Tests:**
   - success → `CONFIRMED/SUCCEEDED`;
   - failure → `FAILED`, retry allowed;
   - cancel → order stays payable until the window expires, then `CANCELLED` and stock released;
   - webhook-only confirmation (browser closed) → confirmed;
   - admin refund → `REFUNDED` and visible in analytics;
   - `reconcile-pending` resolves `CREATION_AMBIGUOUS`.
9. **Acceptance:** all six scenarios recorded with provider IDs in a verification log; no real payments.
10. **Complexity:** M (2 days, plus your Razorpay dashboard access).

### P1-2 · Outbox delivery without Kafka
1. **Status:** a robust outbox (lease, retries, SKIP LOCKED) publishes to Kafka only; the consumers update OpenSearch and order projections.
2. **Problem:** with no broker, nothing downstream runs (D5).
3. **Solution (choose one):**
   - **(a)** provision a reachable Kafka; or
   - **(b)** add an in-process **direct dispatcher** that, when Kafka is not configured, delivers outbox events to the same handlers (search indexer, projection) inside the API. Same idempotency, same retries.
   - **Recommended: (b)** for the current single-instance deployment, keeping Kafka as the multi-instance path.
4. **Backend:** `core/events/outbox_publisher.py`, a handler registry reused from `core/search/consumer.py` and `orders/consumer.py`.
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** a decision on (a) or (b).
8. **Tests:**
   - with Kafka unset, events become `PUBLISHED` and the index document updates after a listing price change;
   - a handler failure retries with backoff;
   - no duplicate processing (idempotent handlers).
9. **Acceptance:** the outbox backlog drains to 0 in a demo; search reflects a price change within one publisher cycle.
10. **Complexity:** M (2–3 days).

### P1-3 · Concurrency-safe periodic jobs
1. **Status:** close auctions, settle group buys, expire RFQs/awards/stream every 15 s, with no row locks.
2. **Problem:** a second API instance (or an overlapping run) could double-settle or double-notify.
3. **Solution:** take a PostgreSQL advisory lock per job (`pg_try_advisory_xact_lock`) and `FOR UPDATE SKIP LOCKED` on the rows each job processes.
4. **Backend:** `core/background.py`; `community`, `auctions`, `exchange`, `pricing/awards`, `sale_stream` services.
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** none.
8. **Tests:** two concurrent job runs → each campaign settled once and one notification per member.
9. **Acceptance:** the concurrency test passes; the job status page is unchanged.
10. **Complexity:** S (1 day).

### P1-4 · Retailer notifications for RFQs, auctions and orders
1. **Status:** customers get in-app notifications; retailers get none and must poll their pages.
2. **Problem:** retailers miss 90-second auctions and new RFQs; this is the brief's "bid notifications" requirement.
3. **Solution:** extend the existing in-app notification model to retailer users, covering:
   - a new RFQ in their area;
   - an auction they can supply;
   - a bid outcome;
   - a new paid order.
   This reuses the existing bell and notification list. **New notification types are a product decision.**
4. **Backend:** `core/notify.py`, `exchange`, `auctions`, `orders` services.
5. **Frontend:** none if the existing bell lists retailer notifications (to verify); otherwise a data-only change.
6. **Database:** possibly a `recipient_role` column, or reuse `customer_id` as `user_id` *(to confirm)*.
7. **Dependencies:** your approval.
8. **Tests:** each event creates exactly one notification for each eligible store.
9. **Acceptance:** retailer unread count increases on each event.
10. **Complexity:** S–M (1–2 days).

### P1-5 · Functional translation coverage
1. **Status:** infrastructure complete (12 languages, persistence, RTL). Coverage is incomplete:
   - ≈32 % of page strings go through `t()`;
   - 290/633 keys are translated per language;
   - 0 catalogue content translations;
   - a small search lexicon;
   - API error messages are English.
2. **Problem:** core shopping and operations pages stay English in every language.
3. **Solution:**
   - **(i)** replace hard-coded strings with `t()` keys on the listed pages **without changing markup or styles**;
   - **(ii)** fill the dictionaries for all 11 languages (machine-assisted, marked for native review);
   - **(iii)** seed `content_translations` for categories and demo products, and use them in catalogue responses when a language is requested;
   - **(iv)** expand the search lexicon for common product nouns;
   - **(v)** keep error codes stable; the frontend already maps codes to `errors.<CODE>`.
4. **Backend:** a catalogue response language parameter; lexicon data.
5. **Frontend:** string replacement only, verified with a visual-diff screenshot check per page (no pixel change in English).
6. **Database:** translation rows (data only).
7. **Dependencies:** none; native review recommended.
8. **Tests:**
   - an i18n coverage test per page (target ≥ 95 % of visible strings);
   - every key exists in `en`;
   - placeholders are preserved;
   - an English screenshot diff of zero changes per page;
   - category names returned in Hindi when requested.
9. **Acceptance:** the coverage scanner reports ≥ 95 % for customer checkout and order pages and ≥ 90 % overall; Urdu remains RTL; the English UI is pixel-identical.
10. **Complexity:** L (5–7 days).

### P1-6 · OCR provider integration
1. **Status:** an HTTP adapter with a documented contract, confidence display and labelled manual fallback; no provider configured.
2. **Problem:** photo lists can't be read.
3. **Solution:** a thin adapter service (or a direct client) for the chosen provider. Google Cloud Vision `DOCUMENT_TEXT_DETECTION` handles handwriting and Indic scripts; Azure AI Vision Read is the alternative. It must return text plus per-line confidence. Manual entry stays as the fallback.
4. **Backend:** `vision/providers.py` (provider client), config.
5. **Frontend:** none (the photo input already appears when OCR is available).
6. **Database:** none.
7. **Dependencies:** **provider choice, account and cost approval**; credentials kept in `.env`.
8. **Tests:**
   - recorded-response tests for printed, handwritten and Hindi lists;
   - low-confidence lines flagged;
   - provider timeout → 502 and the manual path still works;
   - quantities parsed.
9. **Acceptance:** ≥ 80 % of lines correct on a 20-image sample set; no fabricated text.
10. **Complexity:** M (2–3 days, excluding provider onboarding).

### P1-7 · LLM-assisted negotiator with rule-engine guardrails
1. **Status:** a deterministic negotiator with a floor, a 3-round cap, expiry, persisted sessions and multilingual templates; no LLM.
2. **Problem:** the brief asks to investigate a real LLM. Price decisions must stay safe.
3. **Solution:** the **rule engine keeps deciding every price.** An LLM is used only to (a) understand free-text customer messages ("can you do 80k?") into a structured counter-offer, and (b) phrase replies in the customer's language. Prompt-injection safety: the LLM never sees the floor and its output is validated against the engine's numbers. Timeout or error falls back to the current templates. The response states `ai_provider_configured`.
4. **Backend:** `negotiation/service.py` (adapter hook), a new `negotiation/llm.py`, config.
5. **Frontend:** none required; free-text input only if you approve a UI change.
6. **Database:** store the model name per session message (optional column).
7. **Dependencies:** **provider choice, cost and data policy**.
8. **Tests:**
   - the LLM proposes a price below the floor → engine clamps;
   - injection text → no floor disclosure;
   - provider down → template fallback;
   - Hindi replies.
9. **Acceptance:** no agreed price ever goes below the floor across 1,000 fuzzed conversations; fallback is under 1 s.
10. **Complexity:** M (3 days).

### P1-8 · Test-database isolation
1. **Status:** tests share a persistent `basket_db_test`; fixtures are not cleaned. This caused two intermittent failures in the release audit.
2. **Problem:** catalogue-wide tests depend on leftovers from earlier or targeted runs.
3. **Solution:** truncate data tables at session start (after migrate, re-seed the baseline catalogue), keeping per-test uniqueness.
4. **Backend:** `tests/conftest.py`.
5. **Frontend:** none.
6. **Database:** test DB only.
7. **Dependencies:** none.
8. **Tests:** the full suite passes 3× in a row, plus a targeted-then-full sequence.
9. **Acceptance:** no order-dependent failures.
10. **Complexity:** M (1–2 days).

### P1-9 · Logging hygiene
1. **Status:** `DEBUG=true` turns on full SQLAlchemy echo (each statement logged twice). There's no structured job log.
2. **Problem:** noisy logs hide real errors; it took the audit thousands of lines to find the auction 500.
3. **Solution:** a separate `SQL_ECHO` flag (default off), keep `DEBUG` for app logging, and log one structured line per background-job run (name, duration, rows).
4. **Backend:** `core/database.py`, `core/background.py`, `core/config.py`.
5. **Frontend:** none.
6. **Database:** none.
7. **Dependencies:** none.
8. **Tests:** config test; the log contains no SQL by default.
9. **Acceptance:** API log size per probe run drops by over 90 %; errors are still logged with request IDs.
10. **Complexity:** S (½ day).

---

## P2 — Advanced improvements and scalability

| ID | Existing status | Problem | Proposed solution | Backend | Frontend | Database | Dependencies | Tests | Acceptance | Complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2-1 Object storage | Local disk, validated uploads | Files lost or inconsistent across instances | S3-compatible backend behind `media/storage.py`; private documents via signed URLs | `media/storage.py`, config | none | none (URLs unchanged) | Provider/bucket | Upload, serve, private-doc access, migration of existing files | Two API instances serve the same image | M |
| P2-2 Abuse limits | Per-entity duplicate checks exist | Unlimited RFQs/auctions/demand signals per user | Per-user rate limits (e.g. 5 open RFQs, 3 auctions/hour, 20 signals/day) | exchange, auctions, demand | none | none | Limits approval | Limit exceeded → 429 | Limits enforced | S |
| P2-3 Price-history integrity | Ticks written on price change | No guarantee of one tick per listing per day; gaps hide history | Daily snapshot job (idempotent upsert); gap report in the admin quality endpoint | price_intel | none | Unique (listing, day) exists | P1-3 | Snapshot idempotent; gaps reported | 90-day chart has no missing days | S |
| P2-4 Returns and refunds E2E | APIs exist; refunds admin/internal only | Not exercised against the sandbox | Sandbox run: customer return → admin approve → refund → Razorpay refund ID | payments, orders | none | none | P1-1 | Full and partial refund | Refund recorded with provider ID | M |
| P2-5 API performance | No measurements | Unknown query counts on catalogue, cart, quote | Measure query count and latency on top endpoints; add indexes / `selectinload` where justified | various | none | Indexes via migration | — | Query-count assertions | p95 < 300 ms locally on demo data | M |
| P2-6 Group-buy payment option | Group price applied at normal checkout after success | Members can drop out after success | Optional commit-to-pay (authorise on join, capture on success) | community, payments | UI needed | New fields | **New feature — approval required** | — | — | L |
