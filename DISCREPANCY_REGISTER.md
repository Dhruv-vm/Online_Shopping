# BASKET — Discrepancy Register & Technical Debt Log

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Target Audience:** Engineering Leads, System Auditors, Claude Development Team  
> **Last Updated:** 2026-11-20  

---

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
