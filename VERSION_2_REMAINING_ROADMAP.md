# BASKET — Version 2.0 Remaining Roadmap (after the final functional cycle — FROZEN)

> Functional freeze declared 2026-11-21: no new features until the owner approves a new cycle. Everything still open is listed here. UI/UX stays frozen until a separate approval. Statuses as in `VERSION_2_FEATURE_TRACKER.md`.

## Carry-over from Phase C
- **C1 Razorpay:** CLOSED BY OWNER in the final cycle; not reopened.
- **Live OpenSearch indexing:** DONE against a local OpenSearch 2.13 (Kafka mode); Aiven cluster not used.
- **Order projection on a real order event (Kafka mode):** not observed live (needs a paid checkout); covered by tests.

## Phase D — Functional completion
### D1 Multilingual coverage — PARTIALLY COMPLETED (open)
Measured 21 Nov: dictionaries 45.8 %, UI wiring 34.2 % (checkout 2 %, orders 0 %). Plan and tool: `BASKET_TRANSLATION_ARCHITECTURE.md`, `scripts/i18n-coverage.py`. Original scope:
Cart, checkout, orders, account, retailer and admin pages through `t()` without markup/style change; dictionaries for the 11 languages (machine translations marked `needs_native_review`); placeholders preserved; category and demo product translations returned when a language is requested; search lexicon for common nouns; Urdu stays RTL; API error codes stable. *Acceptance:* ≥ 95 % checkout/order pages, ≥ 90 % overall, English screenshot diff zero, Hindi categories returned.
### D2 Retailer notifications — COMPLETED (final cycle)
New RFQ for the store; auction the store can supply; bid outcome; new paid order. Reuse the existing notification system; one notification per eligible recipient per event; correct unread count; check whether the existing bell already shows retailer notifications before touching the frontend. No other notification types without approval.
### D3 Test-database isolation — COMPLETED (final cycle; `VERSION_2_PHASE_D3_REPORT.md`)
Clean the test database at session start, migrate, seed the baseline catalogue; never touch `basket_db`. *Acceptance:* full suite passes 3× in a row and after a targeted run; no order-dependent failures. (Phase C hit two order-dependent failures when runs overlapped — evidence that this is needed.)

## Phase E — Provider integrations (approval + credentials required)
### E1 Handwritten List to Basket OCR — NEEDS PROVIDER CREDENTIALS
Candidates: Google Cloud Vision Document Text Detection, Azure AI Vision Read. Handwriting and Indic scripts where supported, confidence, matching, quantities, manual fallback kept, private image handling, recorded-response tests, live report.
### E2 LLM-assisted AI Negotiator — NEEDS PROVIDER CREDENTIALS
The rule engine stays the price authority (floor, rounds, platform/deal rules, authorisation); model output validated before any action; no PII/payment data to the model; cost cap; fallback; recorded-response tests; live verification.

## Phase F — Advanced improvements
- **F1 S3-compatible storage** — NEEDS PROVIDER CREDENTIALS. `media/storage.py` abstraction, signed URLs for private documents, migration of existing files, public URLs preserved, two-instance test.
- **F2 Abuse limits** — NEEDS PRODUCT APPROVAL. Proposed: 5 open RFQs, 3 auctions/hour, 20 demand signals/day; HTTP 429.
- **F3 Price-history integrity** — NOT STARTED. Daily idempotent snapshot, no duplicate listing/day, gap report on the admin quality endpoint, 90-day checks.
- **F4 Returns & refunds E2E** — NOT STARTED (needs C1 webhooks). Return request → admin review → approve/reject → refund → Razorpay refund id → order/refund status → analytics; full and partial.
- **F5 API performance** — NOT STARTED. Query counts and p95 for catalogue, search, basket, quote, checkout on demo data; indexes/`selectinload` only where measured; target p95 < 300 ms locally.
- **F6 Group-buy commit-to-pay** — NEEDS PRODUCT APPROVAL. New feature; authorisation/capture, cancellation, expiry, refund, consent and UI policies must be approved first. Existing settlement unchanged until then.

## Other open items recorded in earlier phases
- Checkout discount-code input — COMPLETED (final cycle).
- Fixed-amount offers apply per unit (product decision).
- Partial-capture cancellation keeps the discount use.
- Admin analytics `total_revenue_paise` does not net out refunds (reported separately as `refunded_paise`).
- Pre-existing Alembic drift MC-09.

## Open after the final cycle (need a decision, credentials or more time)
- **Two physical laptops** run-through of `BASKET_TWO_LAPTOP_DEMO_RUNBOOK.md` (only independent browser environments on one Mac were tested).
- **D1 multilingual** to 95 % checkout/orders and 90 % overall, with native review.
- **Reward missions** — NEEDS PRODUCT APPROVAL (reward rules, funding, caps, reversal).
- **Recurring-basket autopay** — NEEDS PRODUCT APPROVAL + provider mandate (Razorpay recurring / UPI AutoPay e-mandate).
- **Real-time over the internet** — a named Cloudflare tunnel (needs a Cloudflare account) for live SSE; quick tunnels fall back to 10 s refresh.
- **Main database `basket_db`** is at migration 0033; apply 0034–0039 (`alembic upgrade head`) when you choose — additive and reversible, never run by this cycle.
- E1, E2, F1–F6 unchanged (see above).
