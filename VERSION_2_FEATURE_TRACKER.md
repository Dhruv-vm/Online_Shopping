# BASKET — Version 2.0 Feature Tracker

> Branch `feature/version-2-development` · baseline `v1.0` (`d517b1a`, unchanged) · updated 2026-11-21 after Phase C.
> Status is evidence-based: **COMPLETED** needs passing tests and, where relevant, live verification. Statuses: COMPLETED · PARTIALLY COMPLETED · NOT STARTED · BLOCKED · NEEDS PRODUCT APPROVAL · NEEDS PROVIDER CREDENTIALS.

| ID | Item | Phase | Status | Evidence / what is missing |
| --- | --- | :---: | --- | --- |
| P0-1 | Dukaan vs Dukaan accept crash | A | COMPLETED | `VERSION_2_PHASE_A_REPORT.md`; tests + live probe |
| P0-3 | Payment initiation idempotency | A | COMPLETED | Phase A report; tests + live sandbox order creation |
| P0-4 | Search fallback when the index is untrusted | A | COMPLETED | Phase A report; extended in C2 for direct mode |
| P0-2 | Discount codes, stacking, minimum order, usage limits | B | COMPLETED (backend) | `VERSION_2_PHASE_B_REPORT.md`; checkout code input deferred (UI approval) |
| P1-1 / C1 | Razorpay sandbox end-to-end | C | PARTIALLY COMPLETED | 4 / 6 scenarios PASS in test mode (`docs/RAZORPAY_SANDBOX_VERIFICATION.md`); failure+retry and webhook-only **BLOCKED — need webhook secret + tunnel** |
| P1-2 / C2 | Outbox delivery without Kafka + per-database index | C | COMPLETED | `OUTBOX_DISPATCH=direct`; 9 tests; live: fresh demo backlog drained to 0, price change delivered in 0.5 s; 6 event producers fixed. Live indexing into a real OpenSearch cluster not exercised (mock + Postgres only) — see Phase C report |
| P1-3 / C3 | Concurrency-safe periodic jobs | C | COMPLETED | Advisory locks + SKIP LOCKED; duplicate auction notification fixed; 7 tests incl. concurrent workers |
| P1-9 / C4 | Logging hygiene | C | COMPLETED | `SQL_ECHO` (default off), one `job_run` line per run, credential redaction; live: 983 → 5 log lines |
| P1-5 / D1 | Multilingual coverage | D | NOT STARTED | — |
| P1-4 / D2 | Retailer notifications | D | NEEDS PRODUCT APPROVAL | Event list to approve |
| P1-8 / D3 | Test-database isolation | D | NOT STARTED | — |
| P1-6 / E1 | OCR provider | E | NEEDS PROVIDER CREDENTIALS | Provider, cost, privacy approval |
| P1-7 / E2 | LLM-assisted negotiator | E | NEEDS PROVIDER CREDENTIALS | Provider, cost cap, data policy approval |
| P2-1 / F1 | S3-compatible media storage | F | NEEDS PROVIDER CREDENTIALS | Provider + bucket approval |
| P2-2 / F2 | Abuse limits | F | NEEDS PRODUCT APPROVAL | Proposed 5 RFQs / 3 auctions per hour / 20 signals per day |
| P2-3 / F3 | Price-history integrity | F | NOT STARTED | — |
| P2-4 / F4 | Returns & refunds E2E (sandbox) | F | NOT STARTED | Depends on C1 completion (webhooks) |
| P2-5 / F5 | API performance | F | NOT STARTED | — |
| P2-6 / F6 | Group-buy commit-to-pay | F | NEEDS PRODUCT APPROVAL | New feature |
| — | Checkout discount-code input | UI | NEEDS PRODUCT APPROVAL | Deferred by decision (UI freeze) |
