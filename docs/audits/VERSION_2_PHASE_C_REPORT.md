# BASKET — Version 2.0 Phase C Report (payments verification & infrastructure reliability)

> Branch `feature/version-2-development` · starting commit `4713437` · commits in §H · `v1.0` → `d517b1a` (unchanged).
> Nothing pushed, merged, deployed or opened as a PR. Phases D–F not started.

## A. Executive summary
- **Implemented and verified:**
  - **C2** — outbox delivery without Kafka (`OUTBOX_DISPATCH=direct`) and database-specific OpenSearch index names. Fixing it exposed **six event producers whose events could never be published in any mode**; they are fixed.
  - **C3** — concurrency-safe periodic jobs. A real duplicate-notification bug was found and fixed.
  - **C4** — logging hygiene (`SQL_ECHO`, structured job logs, credential redaction).
- **C1 — Razorpay test mode, 4 of 6 scenarios PASS with real provider ids:**
  - successful hosted checkout
  - window close → expiry
  - admin refund
  - ambiguous-creation reconciliation
- **Blocked:** C1 *failure + retry* and *webhook-only confirmation*. Both need `RAZORPAY_WEBHOOK_SECRET` and a public tunnel registered in the Razorpay Test Dashboard. Phase C is therefore **not fully complete**.
- **No UI/UX change and no migration.**

## B. Work completed

### C1 — Razorpay sandbox
See `docs/RAZORPAY_SANDBOX_VERIFICATION.md` for evidence and the runbook.
- **Setup:** isolated `basket_c1_demo`, `rzp_test_` keys only, the real BASKET checkout UI from a temporary copy of the frontend on port 3001, and the harness `backups/mc/c1_sandbox.py`.
- **No defects were found in the payment code.**
- **Scenario 1:** the final payment-method step in Razorpay's window was completed outside the automation, during a connection drop (§F).

### C2 — Outbox without Kafka
**`DirectDispatchProducer`** (`app/core/events/direct_dispatch.py`):
- Implements the existing `EventProducer` interface, so the unchanged `OutboxPublisherWorker` keeps everything it already does: `SKIP LOCKED` claims and leases, per-event timeout, retry with backoff, `retry_count`/`last_error`, the PUBLISHED acknowledgement and FAILED after max retries.
- Delivery calls the existing `OpenSearchConsumer` and `OrderProjectionConsumer` `process_record`, which runs the handler and the `consumer_inbox` claim in one transaction keyed by (consumer group, event id). Redelivery — or delivery by a Kafka-mode instance using the same groups — therefore never takes effect twice.
- A consumer that can't process yet raises, so the outbox schedules a retry. Dead letters stay in `consumer_inbox`, because there is no DLQ broker.

**Mode selection:**
- `OUTBOX_DISPATCH` is `kafka` (default) or `direct`. Invalid values fail at startup, and the mode is never switched automatically.
- In `direct` mode, Kafka consumers are not started and `KAFKA_BOOTSTRAP_SERVERS` is ignored, with a warning.

**Per-database index names:**
- Prefix: `<OPENSEARCH_INDEX_PREFIX>_<db name>_<6-hex hash of host:port/db>`, e.g. `basket_basket_v2b_demo_441f2f`.
- No user name or password is used.
- Controlled by `OPENSEARCH_INDEX_PER_DATABASE` (default on).
- The default search alias, write alias and IndexManager now use it. The in-memory mock client pre-wires both name styles.

**Health:**
- **Phase A conditions kept:** the KAFKA_NOT_CONFIGURED check still applies in kafka mode. In direct mode the conditions are: dispatcher running (`OUTBOX_DISPATCHER_NOT_RUNNING` otherwise), index rebuilt from PostgreSQL (`SEARCH_INDEXER_NOT_RUNNING` until then), and outbox backlog fresh.
- `/ready` reports `kafka.status=not_used`, `dispatch`, `dispatcher` and the backlog.
- Admin system health adds `outbox_dispatch`, and the existing Kafka row reports "Not used" in direct mode (data only, same row).

**Producer defects found by the live run and a read-only payload audit across `basket_db`, `basket_db_test` and the demo DB (`backups/mc/v2c_event_payload_audit.py`):**
- `order.created` carried `customer_id`.
- `exchange.request_created`, `demand.pool_created`, `demand.pool_threshold_reached` and `auction.started` carried `pincode`.
- `price.changed` lacked `product_id`.

The envelope's PII and partition guards rejected these events before any delivery, in either mode; with Kafka down this had never surfaced. The payloads were corrected and the guards left untouched. No consumer read the removed fields: the order projection already sets `customer_id=None` by design.

### C3 — Periodic jobs
- **`run_job()`** (`app/core/background.py`):
  - A dedicated lock session holds `pg_try_advisory_xact_lock(<sha256-derived key of the job name>)` for the whole run, so the guarantee also covers jobs that commit internally. Another instance's overlapping run is **skipped**, and its work is picked up next cycle.
  - It's used for reservation expiry, payment reconciliation, SLA escalation and all eight Phase 3 jobs.
  - Failures are logged and re-raised, and the lock is always released.
- **Row claims:** auction closing and group-buy settlement claim rows with `FOR UPDATE SKIP LOCKED`. RFQ, award and stream expiry are already single atomic status-guarded `UPDATE`s.
- **Bug fixed:** `close_ended_auctions` notified the customer whenever the locked auction was `COMPLETED`, even if another worker had already closed it. Two overlapping closers sent **two** notifications; the test fails on the old code with `2 == 1`. Now only this run's ACTIVE → COMPLETED transition notifies.
- Group-buy settlement was already idempotent under its row lock (status re-check). No job captures payments.
- Business rules, durations, calculations and expiry policies are unchanged.

### C4 — Logging
- `SQL_ECHO` (default `false`) replaces `echo=DEBUG`.
- One structured line per job run: `job_run {"job", "run_id", "started_at", "status": ok|skipped|failed, "rows", "duration_ms", "error"}`.
- `SanitizeFormatter` is now installed and masks `scheme://user:***@` and `password/secret/token/api_key/key_secret=***`. Errors stay visible.
- **Live, same requests + 20 s of background jobs with `DEBUG=true`:** 983 lines / 182 KB (512 SQL lines) with v1.0-style echo vs **5 lines / 1.3 KB, 0 SQL** with the new defaults.

## C. Files changed
| File | Why |
| --- | --- |
| `backend/app/core/events/direct_dispatch.py` *(new)* | C2 direct producer, no-broker consumer stand-in, inbox-only dead letters |
| `backend/app/core/background.py` | C3 `run_job` (advisory lock + structured log) for every job; C2 direct-mode dispatcher + index bootstrap |
| `backend/app/core/config.py` | `SQL_ECHO`, `OUTBOX_DISPATCH` (+ validator), `OPENSEARCH_INDEX_PER_DATABASE` |
| `backend/app/core/database.py` | Engine echo from `SQL_ECHO` |
| `backend/app/core/logging.py` | `redact_secrets`, working `SanitizeFormatter` |
| `backend/app/core/search/index.py` | `resolve_index_prefix`; per-database default names |
| `backend/app/core/search/client.py` | Mock client pre-wires both name styles |
| `backend/app/core/search/consumer.py` | Default write alias = this database's |
| `backend/app/core/search/index_health.py` | Direct-mode conditions; `outbox_dispatch_status` |
| `backend/app/modules/search/service.py` | Default search alias = this database's |
| `backend/app/main.py` | Kafka consumers only in kafka mode; `/ready` dispatch info |
| `backend/app/modules/governance/router.py` | `outbox_dispatch` field; Kafka row in direct mode |
| `backend/app/modules/auctions/service.py` | SKIP LOCKED claim; notify only on own transition; no pincode in `auction.started` |
| `backend/app/modules/community/service.py` | SKIP LOCKED claim |
| `backend/app/modules/orders/service.py` | No `customer_id` in `order.created` |
| `backend/app/modules/exchange/service.py`, `demand/service.py` | No `pincode` in event payloads |
| `backend/app/modules/retailer/service.py` | `product_id` in `price.changed` |
| `backend/tests/test_v2_phase_c_jobs_logging.py` *(new)* | 7 tests (C3/C4) |
| `backend/tests/test_v2_phase_c_outbox_direct.py` *(new)* | 9 tests (C2) |
| `backend/tests/test_marketplace_master_sync_audit.py` | Reads this database's search alias instead of the hard-coded shared one (new contract) |
| `docs/RAZORPAY_SANDBOX_VERIFICATION.md` *(new)*, `VERSION_2_PHASE_C_REPORT.md`, `VERSION_2_FEATURE_TRACKER.md`, `VERSION_2_REMAINING_ROADMAP.md` *(new)*, `DISCREPANCY_REGISTER.md` | Documentation |

No frontend files changed.

## D. Database changes
- **No migration.** Head remains `0035_discount_codes_redemptions`; `scripts/verify-migrations.sh` re-run: ALL PASSED.
- `basket_db` was **not** reset or modified; it was only read (the payload audit).
- Isolated databases used: `basket_db_test`; `basket_v2c_demo` and `basket_c1_demo` (built with `reset-demo-db.sh`); and the throwaway `basket_migration_verify`.
- Existing outbox rows that failed validation before the fix are left untouched.

## E. Testing (actual runs, 2026-11-21, final code)
| Check | Result |
| --- | --- |
| `ruff check` / `ruff format --check` | clean / 284 files |
| Backend full suite | **585 passed, 0 failed, 3 skipped** (Phase B: 569; +16 new) |
| Phase A + B regression tests | included above, all pass |
| E2E journeys + role suites | 14 / 14 |
| `scripts/audit-features.sh` | 16 / 16 areas pass |
| `scripts/verify-migrations.sh` | ALL MIGRATION CHECKS PASSED |
| Frontend (untouched) `npm test` / type-check / lint / build | 129/129 · 0 errors · 0 errors · 63 routes |
| C3 concurrency tests | overlapping runs of one job never run together (one skipped); concurrent auction closers → 1 notification; 3 concurrent group-buy settlers → 1 award and 1 notification per member |
| C2 tests | price change reaches search after one publisher cycle; failing handler → retry with backoff → PUBLISHED once; duplicate delivery → one effect; 2 concurrent workers → each event once; explicit mode selection; supervisor runs exactly one dispatcher; index bootstrap then trust; per-database names; all 6 fixed producers publish |
| **Live C2/C4** (`basket_v2c_demo`, direct mode, OpenSearch off) | backlog drained to **0 pending / 0 failed**; price change → `price.changed` + `product.updated` PUBLISHED in 0.5 s; `order.cancelled` processed by the order projection (inbox SUCCEEDED); `/ready` and admin health report direct mode; log volume 983 → 5 lines |
| **Live C1** (Razorpay test mode) | 4 PASS, 1 NOT EXECUTED, 1 BLOCKED — §F |

**Kinds of evidence:**
- Automated tests use the real PostgreSQL test database. Payment-provider calls are mocked in the existing payment tests; Phase C adds no mocked provider tests.
- The C1 results are **real Razorpay test-mode API calls**.

**Not exercised live:** OpenSearch indexing against the real cluster. That would create a new per-database index on the shared Aiven cluster, which I didn't do without approval; indexing is covered with the in-memory client.

**Process note:** two runs that overlapped on the shared test database produced order-dependent failures. Both passed when re-run alone. This is evidence for Phase D3 (test isolation).

## F. Razorpay evidence
| # | Scenario | Status | Provider ids | Expected → actual |
| --- | --- | :---: | --- | --- |
| 1 | Hosted checkout success | PASS* | `order_U2p9vWMR6qR89x`, `pay_U2pCOR8PdXQxZg` | Razorpay: order paid, payment captured (netbanking, ₹369.00 = total). BASKET: attempt SUCCEEDED, capture CAPTURED, order CONFIRMED |
| 2 | Failure + retry | NOT EXECUTED | — | Needs the webhook (or reconciliation of a failed attempt) to observe FAILED; run with scenario 4 |
| 3 | Window closed → expiry | PASS | `order_U2pZUMYyQPN6Od` | Still payable (same Razorpay order); expiry → CANCELLED, attempt FAILED, reservation RELEASED, stock restored |
| 4 | Webhook-only confirmation | BLOCKED | — | Needs `RAZORPAY_WEBHOOK_SECRET` + tunnel + Dashboard webhook |
| 5 | Admin refund | PASS | `rfnd_U2pZ1tl7BLddPb` | Razorpay processed ₹369.00; BASKET refund PROCESSED (via reconciliation), capture REFUNDED, order REFUNDED, analytics `refunded_paise` 36900; same key replays; customer self-refund 403 |
| 6 | Ambiguous creation | PASS | `order_U2pZdtnNgeXQEo` | Initiation blocked 409 while ambiguous; reconciliation recovered the attempt to the real order (PENDING) |

\* The last payment-method step happened in the visible browser while the automation's connection was down, so not by the automation. Server-side processing and the provider state were verified afterwards.

## G. UI/UX confirmation
- **No frontend file changed** (`git diff --stat -- frontend` empty), so there is no visual change and no screenshot comparison was needed.
- The admin health page shows the same rows. In direct mode the Kafka row's *text* says "Not used…" (data only).

## H. Git report
| | |
| --- | --- |
| Starting branch / commit | `feature/version-2-development` / `4713437` |
| Ending branch / commit | `feature/version-2-development` / the docs commit after `3b852bb` |
| Commits | `68ea087` fix(events): six publishable payloads · `3b852bb` feat(infra): C2–C4 code + tests · (this commit) docs |
| Working tree | Clean except the user's untracked `BASKET_DEMO_VERIFICATION_REPORT.md` and `BASKET_LOCAL_DEMO_RUNBOOK.md` (not touched) |

Nothing pushed, merged or deployed. `v1.0` unchanged.

## I. Remaining roadmap tracker
See `VERSION_2_FEATURE_TRACKER.md` (status per item) and `VERSION_2_REMAINING_ROADMAP.md` (full scope). Summary:
- C1 is PARTIALLY COMPLETED; the rest is BLOCKED and NEEDS PROVIDER CREDENTIALS.
- D1 NOT STARTED · D2 NEEDS PRODUCT APPROVAL · D3 NOT STARTED.
- E1 and E2 NEED PROVIDER CREDENTIALS.
- F1 NEEDS PROVIDER CREDENTIALS · F2 NEEDS PRODUCT APPROVAL · F3 NOT STARTED · F4 NOT STARTED (needs C1 webhooks) · F5 NOT STARTED · F6 NEEDS PRODUCT APPROVAL.

## J. Next recommended phase
1. **Finish C1** (about 30 minutes with you): add the webhook secret, register the tunnel URL, then run scenarios 2 and 4 from the runbook.
2. **Phase D3 (test-database isolation)** first in Phase D. It needs no approvals and removes the order-dependent failures seen here.
3. **D1 (translations)** and **D2 (retailer notifications, once the event list is approved)**.

Decide whether to allow a live index run on the OpenSearch cluster.
