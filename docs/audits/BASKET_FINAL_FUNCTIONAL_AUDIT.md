# BASKET — Final Functional Audit (start of the final functional cycle)

> 2026-11-21 · branch `feature/version-2-development` @ `204689a` · `v1.0` → `d517b1a` (unchanged) · working tree clean except the user's untracked `BASKET_DEMO_VERIFICATION_REPORT.md` / `BASKET_LOCAL_DEMO_RUNBOOK.md`.
> Sources: current code (inspected now), automated suites (585 backend / 129 frontend passing at `204689a`), live probes from v1.0 and Phases A–C. This document is the **starting** status; it is updated at the end of the cycle.
> Status values: COMPLETE · PARTIALLY COMPLETE · UI ONLY · BACKEND ONLY · BROKEN · NOT STARTED · BLOCKED · NEEDS APPROVAL.

## 1. Infrastructure

| Component | Found | Status |
| --- | --- | --- |
| PostgreSQL 16 | Homebrew server on the Mac; `basket_db` (dev), `basket_db_test`, isolated `*_demo` DBs | COMPLETE |
| Kafka | Configured in `.env` to a remote Aiven broker whose hostname no longer resolves; `deploy/docker-compose.sandbox.yml` has a Kafka service (never started); Docker Desktop installed but was not running | BLOCKED → being set up locally (Docker, approved) |
| OpenSearch | Remote Aiven cluster in `.env` (shared with `basket_db`); per-database index names since Phase C; compose file has an OpenSearch service | PARTIALLY COMPLETE (never live-indexed from this code) |
| Outbox | Kafka mode (default) and direct mode (Phase C) | COMPLETE (direct, live verified) / Kafka NOT verified |
| Redis / server cache | Not present; nothing in the architecture needs it | n/a |
| Frontend data cache | No query library; API calls use `fetch(..., {cache: "no-store"})`; pages hold data in React state | n/a (see Cache) |
| Real-time | One SSE stream (customer auction live view); everything else refreshes on reload or by polling (retailer auctions every 3 s) | PARTIALLY COMPLETE |
| Docker | `backend/Dockerfile`, `frontend/Dockerfile`, `deploy/docker-compose.sandbox.yml` (postgres, kafka, opensearch, backend, frontend) | PARTIALLY COMPLETE (never run; port clash with the host Postgres) |
| Shared two-laptop demo | No shared deployment, no LAN/tunnel configuration, CORS limited to localhost:3000 | NOT STARTED |

## 2. Core marketplace (v1.0 + Phases A–C)

| Feature | UI | API | DB | Workflow | Tests | Live | Status |
| --- | :-: | :-: | :-: | --- | :-: | :-: | --- |
| Auth & roles (admin/retailer/customer) | ✓ | ✓ | ✓ | complete; business accounts cannot shop | ✓ | ✓ | COMPLETE |
| Retailer onboarding & approval | ✓ | ✓ | ✓ | complete | ✓ | ✓ | COMPLETE |
| Catalogue, listings, images | ✓ | ✓ | ✓ | complete | ✓ | ✓ | COMPLETE |
| Pricing, GST, offers | ✓ | ✓ | ✓ | Phase B policy | ✓ | ✓ | COMPLETE |
| Coupon codes | ✗ | ✓ | ✓ | backend only (Phase B); no checkout field | ✓ | ✓ (API) | BACKEND ONLY → Part 7 |
| Inventory & reservations | ✓ | ✓ | ✓ | complete | ✓ | ✓ | COMPLETE |
| Basket, checkout, Razorpay | ✓ | ✓ | ✓ | complete; payment verification closed by the user | ✓ | ✓ (test mode) | COMPLETE |
| Orders & fulfilment | ✓ | ✓ | ✓ | complete, payment-gated | ✓ | ✓ | COMPLETE (no live push → Part 4) |
| Search | ✓ | ✓ | ✓ | PostgreSQL fallback always correct; OpenSearch untrusted until indexed | ✓ | ✓ (PG) | PARTIALLY COMPLETE (OpenSearch → Part 13) |
| Notifications | ✓ (customer bell) | ✓ | ✓ | customers only; retailers receive none | ✓ | ✓ | PARTIALLY COMPLETE (D2) |
| Governance / audit log / system health | ✓ | ✓ | ✓ | complete | ✓ | ✓ | COMPLETE |

## 3. Phase 3 and advanced features (detail in `PHASE_3_FEATURE_COMPLETION_AUDIT.md` at the end of the cycle)

| Feature | Current state (verified in code) | Status | Addressed in |
| --- | --- | --- | --- |
| Demand Gap | Signals, dedup, unique users, threshold, retailer & admin views; not linked to customer intents | PARTIALLY COMPLETE | Parts 6, 14A |
| Community Buying | Templates, start/join/leave, settlement (now lock-safe), awards, notifications; WhatsApp share link exists (`wa.me`) but no invitation token/expiry; progress not pushed live | PARTIALLY COMPLETE | Parts 4, 9 |
| Customer RFQs | Create, bid, accept → award → checkout; expiry job; retailers not notified | PARTIALLY COMPLETE | D2 |
| AI Negotiator | Rule engine, floor, rounds, expiry, Hindi, uses Phase B pricing | COMPLETE (rule-based); LLM NEEDS APPROVAL | — |
| Dukaan vs Dukaan | Customer side complete (SSE live view, accept fixed in A1). **Retailer side:** list of live auctions polled every 3 s with best bid / own best only — no items & quantities, countdown, rank/outbid state, history, closure or outcome; no demo simulation | PARTIALLY COMPLETE | Part 5 |
| Price Intelligence | History, compare, alerts, daily snapshot job, insights | COMPLETE (gap reporting F3 NOT STARTED) | F3 |
| Sale Stream | Flash deals, price drops, hot sellers, expiry; no Rewind | COMPLETE | — |
| Bharat Multilingual | 12 languages, persistence, RTL; ≈46 % of dictionary keys translated per language, ≈32 % of page strings via `t()`; no catalogue content translations | PARTIALLY COMPLETE | Part 11 |
| List to Basket | Manual entry complete; OCR adapter, no provider | COMPLETE (manual) / OCR NEEDS CREDENTIALS | E1 |
| Customer Intent (`/account/intent`) | Profile, consent, recurring intentions (frequency, budget), memories, suggestions. **Not connected to listings, Demand Gap or retailers; no "what happens next" status** | PARTIALLY COMPLETE | Part 6 |
| Basket Missions (shopping planner) | Goal + budget → planned items, alternatives, replace, add to basket; 42 Phase 2 tests pass. Progress/completion/expiry/history not verified end-to-end | PARTIALLY COMPLETE (to be walked through) | Part 10 |
| Reward missions | No model, API or UI exists; needs reward rules | NEEDS APPROVAL (user decision 2026-11-21) | tracker only |
| Recurring / Monthly Essentials basket | Recurring *intentions* exist (labels only); no scheduled basket, no pre-order check | NOT STARTED | Part 8 |
| Autopay mandates | — | NEEDS APPROVAL / CREDENTIALS | documented only |

## 4. Remaining roadmap items

| Item | Status | Plan |
| --- | --- | --- |
| D1 Multilingual coverage | PARTIALLY COMPLETE | Part 11 |
| D2 Retailer notifications | NOT STARTED (needed for Parts 4/5 visibility) | implement for RFQ, auction, bid outcome, paid order — the four events already approved in the roadmap |
| D3 Test-database isolation | NOT STARTED | Part 16 |
| E1 OCR, E2 LLM negotiator | NEEDS CREDENTIALS / APPROVAL | document & keep prepared |
| F1 S3 storage | NEEDS CREDENTIALS | document |
| F2 Abuse limits | NEEDS APPROVAL (limits) | document |
| F3 Price-history integrity | NOT STARTED | Part 14F |
| F4 Returns & refunds E2E | PARTIALLY COMPLETE (refund verified in C1) | verify return flow in Part 14 |
| F5 API performance | NOT STARTED | measure during final gate |
| F6 Group-buy commit-to-pay | NEEDS APPROVAL | tracker only |

## 5. Cache
No Redis or HTTP cache layer; API fetches are `no-store`. Staleness comes from (a) React state that is never refreshed after another user's change (no push, no refetch on focus), (b) the stale/foreign OpenSearch index (guarded since Phase A, fixed per database in C), and (c) quotes priced at quote time (re-validated on order since Phase B). Full audit: `BASKET_CACHE_AUDIT_AND_FIX_REPORT.md` (Part 12).

## 6. Execution order for this cycle
1. Audit (this document).
2. Shared demo infrastructure: Docker (Kafka, OpenSearch), `basket_shared_demo`, LAN + Cloudflare access, CORS/cookies.
3. Real-time layer (authenticated, role-aware SSE + refetch fallback) and retailer notifications (D2).
4. Dukaan vs Dukaan retailer live bidding + labelled demo simulation.
5. Checkout coupon field; Customer Intent; WhatsApp invitation tokens.
6. D3 test isolation.
7. Cache fixes; Kafka/OpenSearch live verification.
8. Recurring basket (scheduling + pre-order check, no autopay); Missions planner completion.
9. Multilingual coverage.
10. Two-client shared demo test, final gate, documentation, freeze.
