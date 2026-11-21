# BASKET — Version 1.0 Functional Audit

> Audited release: tag **`v1.0`** → commit `d517b1a19ef7baded0ce5999339722b44e8f2588`
> Contained in `integration` @ `d38d6e3` (Merge PR #33), confirmed after `git fetch` on 2026-11-21. Remote and local `v1.0` tag objects are identical.
> Audit performed on branch `feature/version-2-development` (created from `integration` @ `d38d6e3`). **No v1.0 code was modified.**
> Date: 2026-11-21 · Auditor environment: developer Mac, Python 3.12, Node 22, PostgreSQL 16.

---

## 1. Method

| Layer | What was run | Data |
| --- | --- | --- |
| Automated regression | Full backend suite, E2E journeys A–F, role/permission suites, feature audit (`scripts/audit-features.sh`), migration up/down verification (`scripts/verify-migrations.sh`), frontend unit tests, type-check, lint, production build | Isolated `basket_db_test` and throwaway `basket_migration_verify` |
| **Live API + database probe** | 33 checks driving the running API exactly as the frontend does, then reading the resulting rows in PostgreSQL (`backups/mc/v1audit_probe.py`, `v1audit_probe2.py`, results JSON alongside) | Fresh `basket_v1audit_demo`, built with `scripts/reset-demo-db.sh`; API on port 8001, search on PostgreSQL |
| Browser | Playwright walkthrough of customer, retailer and admin journeys (release audit of the same code, `9f7324e` — v1.0 differs from it only in documentation) | `basket_demo` |

Payments: the root `.env` holds **Razorpay test-mode** keys (`rzp_test_…`). Payment initiation reached Razorpay's sandbox and created real sandbox orders. No real money was involved, and no payment was completed in Razorpay's hosted window. OCR, LLM and object storage are not configured.

Status meanings:
- **PASS:** works end to end with correct database effects.
- **PARTIAL:** works, with a verified defect or a missing part.
- **FAIL:** the main flow does not work.
- **NOT VERIFIED:** could not be exercised in this environment.

## 2. Automated regression on v1.0 code

| Suite | Result |
| --- | --- |
| Backend (full) | **538 passed, 0 failed**, 3 skipped (opt-in live-infrastructure tests) |
| E2E journeys A–F + role/permission suites | 14 / 14 |
| Feature audit (16 areas) | all passed |
| Migration verification (0031–0034 up/down/re-up, sequential rollback, FK indexes) | all passed |
| Frontend unit tests / type-check / lint / build | 125 / 125 · 0 errors · 0 errors (1 pre-existing warning) · 63 routes |

The suites are green, but the live probe found defects they do not cover (§4).

## 3. Feature results

### Admin
| Feature | Status | Evidence (live probe unless stated) |
| --- | --- | --- |
| Authentication and role permissions | **PASS** | Admin login → role `admin`; `/admin/overview` 200 for admin, **403** for customer; retailer → `/admin/users` **403**; wrong password 401 `INVALID_CREDENTIALS`. |
| Retailer approval and management | **PASS** | New store registered → `PENDING`; offers blocked (403) while pending; document stored; store listed in admin pending queue; approve → DB `VERIFIED`, reviewer recorded; offer allowed after approval (201). Suspend/reinstate with session revocation: E2E journey C. |
| Product and catalogue management | **PASS** | Admin created product + variant (201); canonical image upload 201 and file served (200); edit persisted in DB; 1 image row. |
| Offers and discounts | **PARTIAL** | Deals stored correctly (7 % → 700 basis points) and applied at checkout. **Defects:** (a) discount **codes are never checked** — a deal with a code is applied to every customer automatically (quote request has no code field; no code comparison in `pricing/`); (b) deals **stack without limit** — two 7 % deals gave 14 % off (₹360.00 → ₹309.60); (c) `min_order_paise` is compared with the **unit** price, not the order total. |
| Moderation and audit logs | **PASS** | Admin cancelled an RFQ with a reason → `CANCELLED`; audit entry recorded with `{"action": "cancel_rfq", "reason": …}`. |
| Demand Gap functionality | **PASS** | Two customers' signals pooled (unique users = 2); repeat signal by the same user deduplicated; admin threshold change 200; pool visible to retailers once the threshold is met. |

### Retailer
| Feature | Status | Evidence |
| --- | --- | --- |
| Registration and onboarding | **PASS** | Registration → onboarding; document stored in DB; invalid GSTIN 422, valid GSTIN normalised to upper case. |
| Admin approval | **PASS** | See Admin › Retailer approval (pending → verified, gated actions unlocked). |
| Product creation and editing | **PASS** | Listing created (201) for a new catalogue variant; price edit persisted (₹2,199 → ₹1,999); price-history tick written; duplicate listing of the same variant 409 `LISTING_ALREADY_EXISTS`. |
| Image upload | **PASS** | Upload 200 and served; declared/actual type mismatch 422 `FILE_CONTENT_MISMATCH`; another store's listing 404. Storage is local disk only. |
| Pricing, taxes and discounts | **PASS** | Quote for 2 × ₹1,999 at 18 % GST: subtotal ₹3,998.00, tax ₹609.86 (GST-inclusive, = 3998 × 18/118). Retailer 10 % listing offer stored as 1000 bps and applied: payable ₹3,998.00 → ₹3,598.20. |
| Inventory management | **PASS** | `DELTA +5` → on-hand 50 → 55; going below zero 400 `NEGATIVE_STOCK_NOT_ALLOWED`; `SET` restored 50. Reservations hold and release stock (see Checkout). Bulk adjust: **NOT VERIFIED** (probe payload rejected 422; covered by automated tests). |
| Order fulfilment | **PASS** | Seeded paid order: PROCESSING → PACKED → SHIPPED → OUT_FOR_DELIVERY → DELIVERED all 200; regression to PACKED 422; DB item status `DELIVERED`. Unpaid order cannot be fulfilled (409). |
| RFQ participation | **PASS** | Retailer bid accepted (201); bid above listed price 422 `BID_ABOVE_LIST_PRICE`. |
| Auction bidding | **PASS** | Bid placed; bid above the basket list price rejected; revised lower bid accepted; customer saw ranking live (browser audit). Acceptance by the customer fails — see Customer › Dukaan vs Dukaan. |

### Customer
| Feature | Status | Evidence |
| --- | --- | --- |
| Authentication | **PASS** | Register/login, `/users/me`, wrong password 401, duplicate email 409 `EMAIL_ALREADY_EXISTS`. Retailer/admin sessions are refused basket and checkout actions (403 `BUSINESS_ACCOUNT_CANNOT_SHOP`, E2E journey F). |
| Product discovery | **PASS** | Catalogue 51 products; search "laptop" 1 result (PostgreSQL engine); product detail 200. Hindi search: see Multilingual. |
| Basket management | **PASS** | Add, update quantity, remove; quantity above stock 422; guest basket (cookie `basket_guest_cart`) merged into the account on sign-in (qty 2). |
| Checkout | **PARTIAL** | Quote → reservation (reserved 0 → 1) → order `PENDING_PAYMENT`; reusing the same quote 409 `QUOTE_ALREADY_CONSUMED`; payment initiation created a **Razorpay sandbox order** (`order_…`); forged signature 400 `SIGNATURE_VERIFICATION_FAILED`; cancel released the reservation (1 → 0). **Defect:** payment initiation without an `Idempotency-Key` (what the checkout page sends) creates a **new Razorpay order on every call** — 2 attempts for one order in DB. With the same key it correctly replays. **NOT VERIFIED:** completing a payment in Razorpay's hosted window, live webhooks, sandbox refunds. |
| Order history | **PASS** | List and detail 200; another customer reading the order 404. |
| Community buying | **PASS** | Start on retailer terms (₹1,04,900 → ₹96,508 group price); duplicate start 409 `ALREADY_STARTED`; join → 2 members; double join 409; leave 200; retailer cannot start (403). Settlement → price award → checkout: automated tests only. |
| RFQs | **PASS** | Request → retailer bid → accept (`AWARDED`) → order total equals the bid (₹1,390.99 vs list ₹1,440.99). The quote *line* still shows the list price; the award is applied to the total. |
| Dukaan vs Dukaan | **FAIL** | Start, live bidding and closing after 90 s work, but **accepting the winning bid crashes (HTTP 500, unhandled `IntegrityError` on `uq_cart_listing`)** whenever the winning store's listing is already in the basket — the normal case when the basket's own store bids. Reproduced twice; the transaction rolls back, so the auction can never be accepted. Root cause in `cart/integration.py: set_customer_cart_lines` (delete + re-insert of the same listing; the INSERT is flushed before the DELETE). Automated test passes only because its winner sells a different listing. |
| Price Intelligence | **PASS** | Listing history and cross-store compare 200; alert created; retailer cut the price below target → alert `TRIGGERED` at ₹1,490 and an in-app notification created. No email/SMS channel. |
| Sale Stream | **PASS** | 3 live events, none expired; add to basket at the stream price (₹1,490 = ₹1,490). No Rewind (by design). |
| AI Negotiator | **PASS** (rule-based) | Session in Hindi (`language=hi`, native-script messages); counter-offer moved the store offer; floor respected; accept → quote; **order total equals the negotiated price** (₹86,176.82). No LLM — deterministic rule engine, labelled as such. |
| Multilingual functionality | **PARTIAL** | 12 languages; preference persists on the account and across logins; invalid code 422; Urdu RTL (browser). Hindi search: lexicon maps known words (`चावल` → rice) but is small ("लैपटॉप" → 0 results). Product/category content translations: **0 rows** — catalogue names are English in every language. UI: ≈32 % of page strings translated (measured); cart, checkout, orders, account and most retailer/admin operations pages are English. |
| List to Basket | **PASS** (manual) · OCR **NOT VERIFIED** | Typed list parsed (3 lines, 1 unmatched, labelled manual entry); matches added to basket (2); photo without a provider → 503 `OCR_PROVIDER_UNAVAILABLE`. No OCR provider configured. |

## 4. Defects found by the audit (not caught by the automated suites)

| # | Severity | Defect | Where |
| --- | --- | --- | --- |
| D1 | **Critical** | Accepting a Dukaan vs Dukaan bid fails with 500 when the winning listing is already in the basket | `backend/app/modules/cart/integration.py`, called from `auctions/service.py: accept` |
| D2 | **High** | Discount codes never checked — coded deals apply to everyone | `pricing/discount_service.py`, `quote_service.py`, quote request schema |
| D3 | **High** | Platform deals stack without limit; `min_order_paise` checked against unit price | `pricing/discount_service.py` |
| D4 | **High** | Payment initiation from the checkout page creates a new Razorpay order per call | `frontend/components/checkout/razorpay-modal.tsx` (no key) + `payments/router.py` (generates a key) |
| D5 | High (environment) | Kafka unreachable: all outbox events stay `PENDING` (83 in `basket_db` since 2026-11-20); the OpenSearch index and order projections are never updated, so search can serve stale or foreign products when OpenSearch is enabled | `core/background.py`, `core/search/consumer.py`, root `.env` |
| D6 | Medium | Periodic Phase 3 jobs (close auctions, settle group buys, expire RFQs) take no row locks — safe only on a single API instance | `core/background.py` + module services |
| D7 | Medium | Retailers receive no notifications (new RFQs, auctions, orders); only customers are notified | `core/notify.py` usage |
| D8 | Low | SQL echo enabled whenever `DEBUG=true` — very noisy logs | `core/database.py` |

## 5. Not verified in this environment

- A payment completed in Razorpay's hosted checkout.
- Live Razorpay webhooks (no public URL, no webhook secret).
- Sandbox refunds.
- OCR with a real provider.
- LLM-based negotiation (none exists).
- Kafka / live OpenSearch sync (broker unreachable).
- Multi-instance behaviour.
- The retailer bulk-inventory endpoint (live).

## 6. Verdict

Version 1.0 covers most marketplace functionality end to end, with correct database effects:
- **Admin:** 5 of 6 features PASS.
- **Retailer:** all 9 PASS (bulk inventory not verified).
- **Customer:** 10 of 13 PASS; checkout and multilingual are PARTIAL, and Dukaan vs Dukaan FAILS at acceptance.

Blocking issues for a demo:
- **D1:** Dukaan vs Dukaan cannot be completed.
- **D2/D3:** discount codes and stacking.
- **D4:** duplicate payment orders.

Everything else is configuration (Razorpay webhooks, OCR, Kafka) or coverage work (translations).
