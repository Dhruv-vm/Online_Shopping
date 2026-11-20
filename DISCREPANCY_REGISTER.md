# BASKET — Discrepancy Register & Technical Debt Log

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Target Audience:** Engineering Leads, System Auditors, Claude Development Team  
> **Last Updated:** 2026-11-20  

---

## P3. Phase 3 Discrepancies & Decisions — 2026-11-20

| ID | Severity | Summary | Status |
| :--- | :---: | :--- | :--- |
| P3-01 | Medium | Search queried an empty in-memory mock index whenever OpenSearch was unconfigured (all dev/sandbox searches returned 0) | **Fixed** |
| P3-02 | High (process) | Root `.env` points at live Aiven services; test runs could write to shared OpenSearch (2 docs written, then removed) | **Fixed** (conftest guard) |
| P3-03 | Medium | Docs claimed HMAC-signed quotes; none exist | **Docs corrected**; server-side quotes are the integrity mechanism |
| P3-04 | Medium | Aiven Kafka bootstrap host does not resolve (service off/deleted); `basket.events.marketplace` topic must be created | **Open — infra** |
| P3-05 | Low | Tracker migration numbers (`0021_demand_gap`…) collided with audit `0021` | Renumbered `0022`–`0030`; tracker §4 records mapping |
| P3-06 | Medium | Community Buying “pre-authorise card” not implemented (no real payments) | **Open — product/payments decision**; members pay at checkout after success |
| P3-07 | Low | Customer-created group buys need a funding rule for the discount | **Open — product decision**; retailer/admin creation implemented |
| P3-08 | Low | AI Negotiator is a deterministic rule engine (no LLM configured); only en/hi message templates | Documented; `language_fallback` flag exposed |
| P3-09 | Low | `next-intl` not adopted; lightweight provider with spec dictionary layout | Documented; migrate during redesign if `[locale]` routing is wanted |
| P3-10 | Medium | Indic lexicon and UI translations are seed quality | **Open — native-speaker review required** |
| P3-11 | Medium | No OCR/vision provider configured; multipart not available | Architecture + HTTP adapter + 503; base64 JSON upload |
| P3-12 | Low | Voice-assisted queries (3H) not implemented | **Open** |
| P3-13 | Low | Demand unique-shopper inflation via guest tokens | **Fixed** (authenticated customers only) |
| P3-14 | Low | Expression unique indexes not declared on models | **Fixed** |
| P3-15 | Low | Phase 3 fixtures disturbed catalogue-dependent tests | **Fixed** (isolated category) |
| P3-16 | Low | No retailer-side notification channel (RFQ/auction/demand alerts rely on dashboards + outbox events) | **Open** — consumers for `basket.events.marketplace` not built |

---


## 0. Audit Status Update — 2026-11-20 (verified against code and tests)

### 0.1 Status of the original register

| ID | Original status | Verified status after audit | Notes |
| :--- | :--- | :--- | :--- |
| DISC-01 | Open | **Open (partially mitigated)** | No upload/object-storage endpoint exists. URL inputs now restricted to absolute http(s) (`core/validation.py`). Presigned uploads need an S3/R2 decision + `boto3`; not added (no new infra dependency without approval). |
| DISC-02 | Open | **Closed — already implemented** | `core/config.py` validators already reject `rzp_test_` keys, missing secrets and weak `INTERNAL_SERVICE_KEY` in production. Webhook signature is mandatory in all environments. |
| DISC-03 | Open | **Closed for client components** | `lib/api/client.ts` attaches `X-CSRF-Token` to every POST/PUT/PATCH/DELETE. No Server Actions perform mutations. |
| DISC-04 | Open | **Open (reframed)** | Root cause was that the outbox publisher never ran. It now runs; events only accumulate while Kafka is down. Pruning of `PUBLISHED` rows still not implemented (deliberately: no data deletion in this assignment). |
| DISC-05 | Open | **Closed — different root cause fixed** | A version guard existed but compared unrelated aggregate counters and dropped valid updates. Now uses DB snapshot time. |
| DISC-06 | Open | **Open (low)** | Service-layer isolation verified (`ProductListing.retailer_id == retailer.id` in all retailer inventory queries). DB-level composite FK not added. |
| DISC-07 | Open | Open | Not in scope. |
| DISC-08 | Open | **Open; endpoints now secured** | Carrier updates remain manual, but are now admin/internal-only with a state machine. No admin UI exists for shipments/returns yet. |
| DISC-09 | Open | Unchanged | Behaviour confirmed correct. |
| DISC-10 | Open | Open | Not added; no measured need. |

### 0.2 New discrepancies found and fixed in this audit

| ID | Severity | Summary | Status |
| :--- | :---: | :--- | :--- |
| AUD-SEC-01 | Critical | Unauthenticated shipment and return-status endpoints (refund/restock abuse) | **Fixed** + tests |
| AUD-SEC-02 | Critical | Customer-callable refunds endpoint | **Fixed** + tests |
| AUD-SEC-03 | High | No return/shipment state machines; failed refunds reported as `REFUNDED` | **Fixed** + tests |
| AUD-SEC-04 | High | Retailers could fulfil unpaid orders; retailer cancellation did not restock/refund | **Fixed** + tests |
| AUD-SEC-05 | Medium | `X-Forwarded-For` spoofing bypassed login rate limiting | **Fixed** + tests |
| AUD-SEC-06 | Medium | Missing CSRF on several cookie-auth mutation routers; substring origin match | **Fixed** + tests |
| AUD-SEC-07 | Low | Session owner not checked on revocation lookup | **Fixed** |
| AUD-SEC-08 | Medium | Unsafe image URL schemes accepted | **Fixed** + tests |
| AUD-REL-01 | High | Outbox publisher never started | **Fixed** (`core/background.py`) |
| AUD-REL-02 | High | No catalogue/inventory events were produced; search stock went stale | **Fixed** + pipeline test |
| AUD-REL-03 | High | Expired reservations never released automatically (stock leak) | **Fixed** + test |
| AUD-REL-04 | High | OpenSearch writes dropped by cross-aggregate version comparison | **Fixed** + test |
| AUD-REL-05 | Medium | Search fallback filtered after pagination; LIKE wildcards; unpriced products matched price filters | **Fixed** + tests |
| AUD-REL-06 | Medium | `/ready` reported Kafka "connected" whenever configured | **Fixed** |
| AUD-DB-01 | Medium | Two model indexes never migrated | **Fixed** (`0021`) |
| AUD-DB-02 | Low | Cosmetic model/migration drift (constraint vs unique index, index names) | **Open** — documented |
| AUD-TEST-01 | Medium | Test fixtures mutate the configured database (`store_inventory` reset) | **Open** — documented; run tests on a dedicated DB |
| AUD-DOC-01 | Low | Docs claimed SQLite tests, Vitest, `tsvector` fallback, passing `alembic check`, 145 endpoints | **Fixed** in docs |
| AUD-OPS-01 | Medium | Login rate limiter is in-memory per process | **Open** — needs shared store (Redis) for multi-replica |
| AUD-OPS-02 | Medium | Guests can hold stock via repeated reservations (no per-client reservation rate limit) | **Open** — mitigated by 10-min TTL now actually enforced |

## 1. Executive Overview

This register tracks architectural discrepancies, contract gaps between frontend and backend, unimplemented integrations, known performance bottlenecks, and edge case behaviours observed across the BASKET platform. Each item is classified by severity, system component, root cause, and the exact remediation action required.

---

## 2. Discrepancy & Technical Debt Matrix

| ID | Category | Severity | Summary | Current Behavior | Target Behavior / Remediation |
| :--- | :--- | :---: | :--- | :--- | :--- |
| **DISC-01** | Media & Storage | Medium | Direct Image URL Strings instead of Object Storage Uploads | Products, variants, and KYC documents accept raw string URLs (`image_url`, `document_url`). | Implement direct multipart S3/R2/GCS presigned upload endpoints (`/api/v1/media/upload`) with MIME-type and size validation. |
| **DISC-02** | Payments | High | Dual-Mode Razorpay Sandbox vs Live Key Validation | In development, Razorpay credentials default to sandbox/mock mode without failing fast if keys are missing. | Enforce strict startup validation: if `ENVIRONMENT=production`, mandate valid live `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`. |
| **DISC-03** | Frontend Auth | Medium | CSRF Token Propagation across Next.js Server vs Client Components | Client components read `X-CSRF-Token` cookie, but Server Actions or direct SSR fetches must manually forward the header. | Standardize `frontend/lib/api.ts` to automatically extract and forward `X-CSRF-Token` across both client and server contexts. |
| **DISC-04** | Messaging | Low | Kafka Degraded Mode Lease Accumulation | When running without a live Kafka broker, `outbox_events` accumulate in the database with status `PENDING`. | Implement a scheduled outbox pruning or archiving worker to avoid table bloat when operating long-term in Kafka-degraded mode. |
| **DISC-05** | Search Sync | Medium | OpenSearch Re-indexing on Out-of-Order Events | Rapid consecutive listing updates can theoretically index stale attributes if Kafka partition ordering is breached. | Introduce a version check or timestamp guard in `OpenSearchConsumer.process_message()` to discard out-of-order event revisions. |
| **DISC-06** | Identity / IDOR | Low | Cross-Tenant Retailer Inventory Isolation | Retailers can only adjust stock for listings linked to their own `retailer_id`. Validated at service layer. | Add an explicit database-level foreign key or composite unique check tying `store_inventories.retailer_id` strictly to `retailer_listings.retailer_id`. |
| **DISC-07** | Intent Memory | Low | Guest Personalization Boundary | Unauthenticated guests cannot create intent profiles; their intent is stored transiently in sessionStorage. | Provide automated hydration of guest preferences into `UserIntentProfile` upon customer registration or login. |
| **DISC-08** | Order Tracking | Medium | Simulated Carrier Tracking Webhooks | Shipment tracking updates are triggered manually via API (`PATCH /api/v1/orders/{id}/shipments/{id}`) rather than live 3PL webhooks (e.g. Shiprocket, Delhivery). | Build 3PL webhook adapter layer once production courier partner APIs are selected. |
| **DISC-09** | Cart Replacement | Low | Quote Invalidation upon Substitute Replacement | Replacing an item via `/api/v1/cart/items/{id}/replace` invalidates existing checkout quotes, requiring the customer to re-quote. | Expected behaviour for security; ensure the frontend UI displays a subtle "Cart updated: recalculating prices" notification rather than a generic error. |
| **DISC-10** | Database Index | Low | Composite Index for High-Volume Listing Lookups | `retailer_listings` has indexes on `retailer_id` and `variant_id`, but lacks composite index on `(is_active, selling_price)` for filtered sorting. | Add composite index `idx_listings_active_price` in next optimization migration. |

---

## 3. In-Depth Analysis of Critical Items

### 3.1 DISC-01: Media & Asset Storage Architecture
- **Current State:** The database stores `image_url` as `VARCHAR(1024)` in `products`, `product_variants`, and `document_url` in `retailer_documents`. The frontend and tests pass placeholder or external static URLs (e.g. Unsplash or Cloudinary URLs).
- **Risk:** No validation that uploaded files are genuine images, no antivirus scanning, and retailers can submit broken external links.
- **Remediation Plan for Claude:**
  1. Add an S3-compatible client in `backend/app/core/storage.py` (supporting AWS S3, Cloudflare R2, or MinIO).
  2. Expose `POST /api/v1/media/presigned-url` granting time-limited presigned PUT URLs.
  3. Validate image dimensions, content type (`image/jpeg`, `image/png`, `image/webp`), and file size ($\le 5\text{ MB}$).

### 3.2 DISC-02: Razorpay Production Safeguards
- **Current State:** `backend/app/modules/payments/service.py` provides fallback sandbox verification for automated testing.
- **Risk:** Accidental deployment to production with mock payments enabled could allow orders to be marked paid without financial settlement.
- **Remediation Plan for Claude:**
  1. In `PaymentService.__init__()`, assert that if `settings.is_production` is `True`, `settings.RAZORPAY_KEY_ID` and `settings.RAZORPAY_KEY_SECRET` are non-empty and do not match test prefix `rzp_test_mock`.
  2. Mandate webhook signature verification in production, raising `PaymentVerificationError` if the signature is missing or invalid.

### 3.3 DISC-05: Kafka & Search Event Idempotency
- **Current State:** `consumer_inbox` deduplicates duplicate message deliveries by storing `message_id`. However, if event updates for the same listing are processed concurrently across different worker threads, older data could overwrite newer data.
- **Remediation Plan for Claude:**
  - In `OpenSearchConsumer`, include `updated_at` or `entity_version` in the OpenSearch document.
  - Use OpenSearch's `version_type=external_gte` to prevent out-of-order overwrites.

---

## 4. Phase 3 Feature Boundary Verification

To avoid regression or architectural confusion during handoff, the following 9 features are confirmed to be **SPECIFICATION ONLY (UNIMPLEMENTED IN CODE)**:
1. **Demand Gap & Unmet Demand Aggregation**
2. **Basket Community Buying (Group Purchasing)**
3. **Basket Community Exchange (Customer-initiated RFQs)**
4. **AI Negotiator (Autonomous deal negotiation)**
5. **Dukaan vs Dukaan (Multi-retailer dynamic bidding)**
6. **Basket Price Intelligence (Historical price trends)**
7. **Sale Stream (Real-time live flash deals feed)** *(Note: Sale Stream Rewind is explicitly excluded)*
8. **Bharat Multilingual (Regional Indian languages)**
9. **Handwritten List to Basket (OCR / vision to cart - optional)**

*None of the above features have database tables, API routes, or backend logic yet.* Claude will implement them starting in Phase 3.
