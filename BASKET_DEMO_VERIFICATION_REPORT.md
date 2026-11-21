# BASKET — Comprehensive Local Demonstration & Feature Verification Report

---

## 1. Local Environment & Git Integrity

| Property | Recorded State | Status |
|---|---|:---:|
| **Repository Path** | `/Users/dhruv/dhruv files/basket/Online_Shopping` | **VERIFIED** |
| **Git Current Branch** | `feature/version-2-development` | **VERIFIED** |
| **Current HEAD Commit** | `8addcd8` (`docs: Version 2.0 Phase A report and discrepancy register entries`) | **VERIFIED** |
| **Working Tree Status** | Uncommitted Phase B draft changes preserved as instructed; zero files overwritten or discarded | **SAFE & PRESERVED** |
| **Release Tag `v1.0`** | `d517b1a19ef7baded0ce5999339722b44e8f2588` | **VERIFIED** |
| **Database Connected** | `basket_demo` on `localhost:5432` (system DB `basket_db` untouched) | **VERIFIED** |
| **Backend Service** | FastAPI running on `http://127.0.0.1:8000` (PID 3888) | **LIVE / PASS** |
| **Frontend Service** | Next.js 15 App Router running on `http://localhost:3000` | **LIVE / PASS** |

---

## 2. Feature Verification Classification

### A. PASS (Fully Functional & Verifiable in Live UI)
1. **Admin Authentication & RBAC:** Admin login, cookie session management, route protection preventing non-admins from accessing `/admin`.
2. **Retailer KYC & Document Review:** Viewing submitted retailer documents, approving and suspending retailer status, and logging actions to `admin_audit_logs`.
3. **Admin Catalogue Governance:** Master product creation, category tree navigation, SKU variant management, and attribute definitions.
4. **Demand Gap Aggregator:** Viewing aggregated unmet demand pools, zero-result search clusters, and out-of-stock demand signals.
5. **Retailer Product Listings & Inventory Management:** Multi-category listing creation, selling price edits, stock count updates, and negative-stock prevention.
6. **Retailer Multi-Stage Order Fulfillment:** Advancing orders through `PROCESSING` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` $\rightarrow$ `DELIVERED`, with strict 409 rejection for unpaid orders.
7. **Customer Quick-Commerce Storefront:** Product browsing across Groceries, Fashion, Electronics, and Beauty; category filtering; search; and detail pages.
8. **Product Passport:** Full display of ingredients, allergens, origin, certifications, and manufacturing details.
9. **Cart & HMAC-Signed Quotes:** Cart management, stock reservation checks, and server-side HMAC-SHA256 signature generation preventing price tampering.
10. **Customer-Only Checkout Guard:** Strict role enforcement ensuring only customer accounts can check out; retailers/admins are routed to their respective dashboards.
11. **Dukaan vs Dukaan (Phase 3E + Phase A Fix):** Reverse auction initiation, competitive bidding, and conflict-free cart acceptance.
12. **Community Buying (Phase 3B):** Retailer volume deal templates, customer campaign creation, initials-based member tracking, and threshold price settlement.
13. **Community Exchange RFQs (Phase 3C):** Customer custom quote requests, retailer bid submissions, bid comparison, and cart conversion.
14. **Sale Stream Flash Deals (Phase 3G):** Polled live feed on homepage with real-time countdowns (Sale Stream Rewind is permanently removed).
15. **Price Intelligence (Phase 3F):** 90-day price trend history charts, competitor store price comparison cards, and in-app price alerts.
16. **Typed List to Basket (Phase 3I):** Textual shopping list parser extracting line items and matching catalog listings.

---

### B. PARTIAL (Functional Infrastructure with Documented Scope Boundaries)
1. **Bharat Multilingual (Phase 3H):**
   - *Status:* Core interface dictionary (header, footer, navigation, badges, auth) is translated across 12 Indian regional languages (English, Hindi, Bengali, Telugu, Marathi, Tamil, Urdu with RTL, Gujarati, Kannada, Odia, Malayalam, Punjabi).
   - *Limitation:* Product catalogue descriptions, technical specifications, and legal policies remain in English (~46% total dictionary key translation coverage).
2. **AI Negotiator / Deal Assistant (Phase 3D):**
   - *Status:* Real-time conversational deal assistant operating over live cart items (`POST /api/v1/assistant/chat`).
   - *Limitation:* Operates deterministically via a rule-based algorithm against retailer floor prices (`mode=rule_based`); it is not an LLM integration.
3. **Discount & Offer Engine:**
   - *Status:* Percentage and fixed retailer offers apply correctly to item calculations.
   - *Limitation:* Version 1 audit identified discount code coupon validation gaps and unlimited discount stacking; comprehensive fix is scheduled for Phase B.

---

### C. AUTOMATED ONLY (Verified via Automated Regression Suites)
1. **Outbox Event Publisher & Kafka Streaming:** Verified via unit and integration tests with transactional outbox event storage.
2. **Payment Webhook HMAC Verification:** Automated tests assert that invalid or missing `X-Razorpay-Signature` headers are rejected with `PaymentVerificationError`.
3. **Concurrent Inventory Reservations:** Stress tests verify that simultaneous checkout attempts on a single inventory unit allow exactly one winner without overselling.

---

### D. NOT VERIFIED / ENVIRONMENT DEPENDENT
1. **Vision OCR Image Parsing (Phase 3I):** Unstructured text list parsing is verified; camera photo/image OCR requires a live Google Cloud Vision or external OCR provider API key (surfaces typed 503 `OCR_PROVIDER_UNAVAILABLE` when unconfigured).
2. **Live Hosted Payment Gateway Settlement:** Razorpay order creation and sandbox payment verification work; end-to-end hosted checkout popup flow requires a live merchant portal activation.
3. **Cloud Media Storage (S3/R2):** Image and KYC document uploads use local filesystem storage; cloud object storage integration is planned.
4. **SMS / Email Alerts:** Price alerts and order updates generate internal database notifications (`customer_notifications`); external SMS/Email gateways are unconfigured.

---

### E. FAIL (Defects Identified or Historical Issues)
1. *Resolved in Phase A:* Dukaan vs Dukaan winning bid acceptance previously crashed with HTTP 500 duplicate key error when the winning listing was already in the cart. **Verified FIXED in commit `dfed80a` (test passed).**
2. *Resolved in Phase A:* Re-clicking "Pay" previously created duplicate Razorpay orders. **Verified FIXED in commit `bf6919e` (idempotency key reuses pending attempt).**
3. *Resolved in Phase A:* OpenSearch index drift returned stale or cross-database products. **Verified FIXED in commit `654343c` (automatic PostgreSQL fallback when indexer is unconfigured or degraded).**

---

## 3. Version 2 Phase A Verification Summary

The three critical resilience fixes delivered in Phase A were verified live:

```
tests/test_v2_phase_a_cart_lines.py::test_auction_accept_when_winning_listing_already_in_basket PASSED
tests/test_v2_phase_a_cart_lines.py::test_auction_accept_other_store_replaces_line_and_keeps_later_items PASSED
tests/test_v2_phase_a_cart_lines.py::test_rfq_accept_when_listing_already_in_basket PASSED
tests/test_v2_phase_a_cart_lines.py::test_list_to_basket_when_listing_already_in_basket PASSED
tests/test_v2_phase_a_cart_lines.py::test_residual_unique_violation_becomes_409 PASSED

tests/test_v2_phase_a_payment_idempotency.py::test_repeat_without_key_reuses_pending_attempt PASSED
tests/test_v2_phase_a_payment_idempotency.py::test_repeat_with_same_key_replays_and_keyless_then_reuses PASSED
tests/test_v2_phase_a_payment_idempotency.py::test_new_attempt_allowed_after_failed_attempt PASSED
tests/test_v2_phase_a_payment_idempotency.py::test_five_concurrent_keyless_initiations_create_one_attempt PASSED
tests/test_v2_phase_a_payment_idempotency.py::test_different_explicit_keys_still_behave_as_before PASSED

tests/test_v2_phase_a_search_fallback.py::test_engine_decision_for_each_pipeline_state PASSED
tests/test_v2_phase_a_search_fallback.py::test_outbox_backlog_means_stale_index PASSED
tests/test_v2_phase_a_search_fallback.py::test_untrusted_index_is_never_queried PASSED
tests/test_v2_phase_a_search_fallback.py::test_trusted_index_is_used PASSED
tests/test_v2_phase_a_search_fallback.py::test_configured_cluster_without_kafka_falls_back_by_default PASSED
tests/test_v2_phase_a_search_fallback.py::test_health_endpoints_report_search_engine PASSED

Result: 16 passed in 4.99s (100% PASS)
```

---

## 4. State Propagation Architecture: What Happens on Retailer Updates

When a retailer modifies data in the portal, state propagation follows standard transactional semantics:

1. **Price Update (`PATCH /api/v1/retailer/listings/{id}`):**
   - The new price is committed to `product_listings.selling_price_paise`.
   - An immutable tick is recorded in `price_history_ticks`.
   - *Customer Experience:* When the customer loads or refreshes the product page, Next.js queries `/api/v1/products/{id}`, rendering the new price. Cart and checkout quotes immediately compute against the updated price.
   - *Sync Model:* PostgreSQL database persistence + HTTP query on fetch/refresh. **It is not an automatic WebSocket live push.**
2. **Stock Quantity Update (`PATCH /api/v1/retailer/inventory/{id}`):**
   - `store_inventory.on_hand_quantity` is updated immediately.
   - Available quantity is recomputed (`on_hand - reserved`).
   - If stock reaches 0, product card displays "Out of Stock" badge on the next render.
3. **Offer Creation (`POST /api/v1/retailer/offers`):**
   - An offer row is inserted with basis-point discount value.
   - The pricing engine evaluates eligible items upon quote calculation.
4. **Order Status Update (`PATCH /api/v1/retailer/orders/{id}/status`):**
   - Transitions order from `CONFIRMED` $\rightarrow$ `PROCESSING` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` $\rightarrow$ `DELIVERED`.
   - Updates `orders.status` and logs an entry to `order_status_history`.
   - Customer sees the new milestone when viewing `/orders` or `/orders/[id]/track`.

---

## 5. Strict Read-Only Confirmation

- Zero application source files modified.
- Zero frontend components, CSS, or styling altered.
- Zero database schemas, migrations, or shared database tables touched.
- `basket_db` remains completely unmolested; demo data operates out of `basket_demo`.
- No Git commits, pushes, PRs, merges, or branch changes were made.
