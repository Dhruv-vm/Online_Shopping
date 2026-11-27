# BASKET — Version 2.0 Feature Tracker

> Branch `feature/version-2-development` · baseline `v1.0` (`d517b1a`, unchanged) · updated 2026-11-21 at the end of the final functional cycle (functional freeze).
> Status is evidence-based: **COMPLETED** needs passing tests and, where relevant, live verification. Statuses: COMPLETED · PARTIALLY COMPLETED · NOT STARTED · BLOCKED · NEEDS PRODUCT APPROVAL · NEEDS PROVIDER CREDENTIALS.

| ID | Item | Phase | Status | Evidence / what is missing |
| --- | --- | :---: | --- | --- |
| P0-1 | Dukaan vs Dukaan accept crash | A | COMPLETED | `VERSION_2_PHASE_A_REPORT.md`; tests + live probe |
| P0-3 | Payment initiation idempotency | A | COMPLETED | Phase A report; tests + live sandbox order creation |
| P0-4 | Search fallback when the index is untrusted | A | COMPLETED | Phase A report; extended in C2 for direct mode |
| P0-2 | Discount codes, stacking, minimum order, usage limits | B | COMPLETED (backend) | `VERSION_2_PHASE_B_REPORT.md`; checkout code input deferred (UI approval) |
| P1-1 / C1 | Razorpay sandbox end-to-end | C | CLOSED BY OWNER | Owner declared payment work sorted and closed (final cycle); not reopened |
| P1-2 / C2 | Outbox delivery without Kafka + per-database index | C | COMPLETED | `OUTBOX_DISPATCH=direct`; 9 tests; live: fresh demo backlog drained to 0, price change delivered in 0.5 s; 6 event producers fixed. Live indexing into a real OpenSearch cluster not exercised (mock + Postgres only) — see Phase C report |
| P1-3 / C3 | Concurrency-safe periodic jobs | C | COMPLETED | Advisory locks + SKIP LOCKED; duplicate auction notification fixed; 7 tests incl. concurrent workers |
| P1-9 / C4 | Logging hygiene | C | COMPLETED | `SQL_ECHO` (default off), one `job_run` line per run, credential redaction; live: 983 → 5 log lines |
| P1-5 / D1 | Multilingual coverage | D | PARTIALLY COMPLETED | Architecture + `scripts/i18n-coverage.py`; measured 45.8 % dictionaries, 34.2 % UI wiring (checkout 2 %, orders 0 %); targets 95/90 % not met — `BASKET_TRANSLATION_ARCHITECTURE.md` |
| P1-4 / D2 | Retailer notifications | D | COMPLETED | RFQ in area, auction the store can supply, auction closed, won/not selected, paid order; one notice per recipient (atomic close); tests + live |
| P1-8 / D3 | Test-database isolation | D | COMPLETED | Drop/recreate/migrate/seed per session, run lock, protected DB names; full suite 3× + targeted→full — `VERSION_2_PHASE_D3_REPORT.md` |
| P1-6 / E1 | OCR provider | E | NEEDS PROVIDER CREDENTIALS | Provider, cost, privacy approval |
| P1-7 / E2 | LLM-assisted negotiator | E | NEEDS PROVIDER CREDENTIALS | Provider, cost cap, data policy approval |
| P2-1 / F1 | S3-compatible media storage | F | NEEDS PROVIDER CREDENTIALS | Provider + bucket approval |
| P2-2 / F2 | Abuse limits | F | NEEDS PRODUCT APPROVAL | Proposed 5 RFQs / 3 auctions per hour / 20 signals per day |
| P2-3 / F3 | Price-history integrity | F | NOT STARTED | — |
| P2-4 / F4 | Returns & refunds E2E (sandbox) | F | NOT STARTED | Depends on C1 completion (webhooks) |
| P2-5 / F5 | API performance | F | NOT STARTED | — |
| P2-6 / F6 | Group-buy commit-to-pay | F | NEEDS PRODUCT APPROVAL | New feature |
| — | Checkout discount-code input | UI | COMPLETED | Approved UI addition; applied / not applicable / invalid states verified on live quotes |

## Final cycle additions

| ID | Item | Status | Evidence |
| --- | --- | --- | --- |
| FC-1 | Shared two-laptop demo (Docker Kafka/OpenSearch, LAN + tunnel, one origin) | COMPLETED (independent client environments); two physical laptops NOT TESTED | `BASKET_SHARED_DEMO_TEST_REPORT.md` |
| FC-2 | Authenticated, role-aware live updates (SSE + fallback) | COMPLETED | `BASKET_REALTIME_SYNC_REPORT.md` |
| FC-3 | Dukaan vs Dukaan retailer live bidding + demo simulation | COMPLETED | `test_final_dukaan_live.py` |
| FC-4 | Customer intent workflow | COMPLETED | `BASKET_INTENT_DEMO_GUIDE.md` |
| FC-5 | Recurring basket (Monthly Essentials) — scheduling + pre-order check | COMPLETED | `RECURRING_BASKET_IMPLEMENTATION_REPORT.md` |
| FC-6 | Autopay mandates | NEEDS PRODUCT APPROVAL + PROVIDER | same report |
| FC-7 | WhatsApp group invitations | COMPLETED | `WHATSAPP_GROUP_INTEGRATION.md` |
| FC-8 | Basket Missions planner completion | COMPLETED | `MISSIONS_FUNCTIONAL_COMPLETION_REPORT.md` |
| FC-9 | Reward missions | NEEDS PRODUCT APPROVAL | same report |
| FC-10 | Kafka consumers on a real broker (4 defects) + OpenSearch live indexing | COMPLETED | `KAFKA_INFRASTRUCTURE_AND_VERIFICATION.md` |
| FC-11 | Cache audit (no-store API, same-origin SSR) | COMPLETED | `BASKET_CACHE_AUDIT_AND_FIX_REPORT.md` |
