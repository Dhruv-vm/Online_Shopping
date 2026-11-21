# BASKET — Local Application Demonstration Runbook

---

## A. Local Application Details & Runtime Architecture

| Component | URL / Endpoint | Details / Commands |
|---|---|---|
| **Customer Storefront** | [http://localhost:3000](http://localhost:3000) | Next.js 15 Quick-Commerce Storefront |
| **Retailer Portal** | [http://localhost:3000/retailer](http://localhost:3000/retailer) | Retailer Operations & B2B Inventory Console |
| **Admin Governance Portal** | [http://localhost:3000/admin](http://localhost:3000/admin) | Platform Admin, KYC & Moderation Console |
| **Backend API Base** | [http://localhost:8000](http://localhost:8000) | FastAPI (Python 3.12, Uvicorn) |
| **Interactive API Documentation**| [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for all 145+ REST endpoints |
| **Alternative API Docs** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | ReDoc Schema Documentation |
| **Active Demo Database** | `basket_demo` on `localhost:5432` | Isolated demo DB with 50 products, 78 listings, 7 users |
| **Liveness Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | `{"status":"ok","service":"basket-backend"}` |
| **Readiness Health Check** | [http://localhost:8000/ready](http://localhost:8000/ready) | Reports DB, Kafka, search fallback status |

### Startup Commands (To run anytime in separate terminal tabs)

#### Tab 1 — Backend (FastAPI with isolated Demo DB):
```bash
cd "/Users/dhruv/dhruv files/basket/Online_Shopping/backend"
DATABASE_URL="postgresql+asyncpg://dhruv@localhost:5432/basket_demo" OPENSEARCH_URL="" .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```
> **Search Engine Fallback Note:** Running with `OPENSEARCH_URL=""` enables PostgreSQL full-text search directly against the demo database, ensuring search returns only demo products and avoids cross-database index pollution.

#### Tab 2 — Frontend (Next.js 15):
```bash
cd "/Users/dhruv/dhruv files/basket/Online_Shopping/frontend"
npm run dev
```

#### How to Stop the Application:
Press `Ctrl + C` in both terminal windows, or run:
```bash
kill $(lsof -t -i :8000) 2>/dev/null
kill $(lsof -t -i :3000) 2>/dev/null
```

---

## B. Demo Account Instructions

All accounts are pre-seeded in `basket_demo` and use the standardized development password:
**`Basket@123`**

*(Note: Never reveal credentials or store passwords in production environments.)*

| Role | Account Email | Initial Landing View | Primary Capabilities to Demonstrate |
|---|---|---|---|
| **Platform Administrator** | `admin@basket.demo` | `/admin` | KYC review, category governance, platform deals, demand analytics, audit logs |
| **Retailer 1 (Basket Mart)** | `retailer1@basket.demo` | `/retailer` | Groceries & staples inventory, price updates, order fulfillment, offers |
| **Retailer 2 (Basket Lifestyle)** | `retailer2@basket.demo` | `/retailer` | Apparel & clothing catalog, reverse auctions (Dukaan vs Dukaan) |
| **Retailer 3 (Basket Electronics)** | `retailer3@basket.demo` | `/retailer` | Electronics, specs, Community Exchange RFQ bidding |
| **Retailer 4 (Basket Beauty)** | `retailer4@basket.demo` | `/retailer` | Cosmetics, personal care, floor-price margin rules |
| **Customer 1 (Shopper)** | `customer@basket.demo` | Storefront `/` | Search, cart, quote, checkout, group buying, price alerts |
| **Customer 2 (Multi-User Tests)** | Register at `/register` | Storefront `/` | Register new customer or use incognito browser for multi-buyer workflows |

> **Presentation Tip:** Use a **Standard Browser Window** for the Retailer/Admin session and a separate **Incognito / Private Window** for the Customer session so cookie authentication sessions do not overwrite each other.

---

## C. Feature Verification & Audit Matrix

| Role | Feature | Status | Navigation | Demonstration Steps | Expected Result | Documented Limitations |
|---|---|:---:|---|---|---|---|
| **Admin** | **A1. Admin Authentication** | **PASS** | `/login` | Enter `admin@basket.demo`, submit | Redirects to `/admin`; sets admin JWT; non-admin blocked (403) | Session timeout requires re-login |
| **Admin** | **A2. Retailer Management** | **PASS** | `/admin/retailers` | View submitted KYC documents; click Approve / Suspend | Verification status updates; updates retailer's publishing access | Rejection comments are recorded in audit logs |
| **Admin** | **A3. Catalogue Management** | **PASS** | `/admin/catalogue` | View products, edit brand, add category node | Global category tree updates; variants linked to master SKU | Category deletion blocked if active listings exist |
| **Admin** | **A4. Platform Deals & Offers** | **PASS** | `/admin/deals` | View deals; toggle active flag; create discount | Platform discount rule created with basis points | Discount code validation and stacking logic is Phase B |
| **Admin** | **A5. Demand Gap Aggregator** | **PASS** | `/admin/demand` | Inspect unmet search demand by pincode and category | Real-time demand pools visualized with threshold signals | Trends require search activity to populate |
| **Admin** | **A6. Governance & Audit Logs** | **PASS** | `/admin/audit-logs` | Filter actions by entity (`RETAILER`, `ORDER`, `DISCOUNT`) | Immutable audit trail displaying admin ID, action, and timestamp | In-app view only; CSV export is planned |
| **Retailer** | **R1. Onboarding & KYC** | **PASS** | `/retailer/onboarding` | Submit GSTIN, PAN, and store profile | Status shows `PENDING_REVIEW` until admin approval | File upload uses local disk storage |
| **Retailer** | **R2. Listing Management** | **PASS** | `/retailer/listings` | Select catalog SKU, set selling price and MRP | Listing created; appears in store catalog | Image URL validation checks format |
| **Retailer** | **R3. Price Management** | **PASS** | `/retailer/listings` | Edit selling price, click Save | Price updated in DB; appends tick to `price_history_ticks` | Customer sees new price upon page refresh / quote |
| **Retailer** | **R4. Inventory & Stock** | **PASS** | `/retailer/inventory` | Update `on_hand_quantity`, inspect available stock | `available_quantity = on_hand - reserved`; negative stock blocked | Stock reservations expire after 15-minute TTL |
| **Retailer** | **R5. Order Fulfillment** | **PASS** | `/retailer/orders` | Advance status `CONFIRMED` $\rightarrow$ `PROCESSING` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` | Order status history recorded; customer sees progress | Unpaid orders strictly blocked with 409 `ORDER_NOT_PAID` |
| **Retailer** | **R6. RFQ Bidding** | **PASS** | `/retailer/exchange` | View customer RFQs, enter quote price, submit bid | Bid posted to customer's RFQ compare sheet | Retailer can only bid on relevant categories |
| **Retailer** | **R7. Group Buy Templates** | **PASS** | `/retailer/community-buying` | Publish volume discount template (e.g. 5+ buyers = 15% off) | Template available for customers to initiate campaigns | Stock safety checks enforce inventory reservation |
| **Customer** | **C1. Storefront Discovery** | **PASS** | `/` & `/products` | Filter by category (Groceries, Fashion, Electronics), sort | Filtered grid with real-time stock and discount badges | OpenSearch uses PostgreSQL fallback if index unconfigured |
| **Customer** | **C2. Intent Memory & Missions** | **PASS** | `/account/intent` & `/missions` | Review past purchases; generate mission basket | Goal-oriented basket prepopulated | Intent requires purchase history to personalize |
| **Customer** | **C3. Cart & HMAC Quote** | **PASS** | `/cart` & `/checkout` | Add items, select address, generate quote | Server signs HMAC quote; guarantees price tampering protection | Only customer accounts can check out (shopper guard) |
| **Customer** | **C4. Community Buying** | **PASS** | `/community-buying` | Browse active group buys; join campaign | Member initials added; progress bar advances toward threshold | Checkout unlocked once group threshold reached |
| **Customer** | **C5. Community Exchange (RFQ)**| **PASS** | `/exchange` | Create RFQ with target budget and delivery date | RFQ published to verified retailers | Admin can moderate/cancel abusive RFQs |
| **Customer** | **C6. Dukaan vs Dukaan** | **PASS** | `/auctions` | Start 90s reverse auction on cart items | Local retailers bid down; Phase A cart conflict resolved | Winning bid replaces line without 500 duplicate crash |
| **Customer** | **C7. Price Intelligence** | **PASS** | `/products/[id]` & `/account/price-alerts`| View 90-day price trend chart; set price alert | Visual price trend rendered; alert triggered on price drops | In-app alerts only; external SMS/Email not configured |
| **Customer** | **C8. AI Negotiator** | **PASS** | `/assistant` | Chat with deal assistant on cart discount | Deterministic rule-based ladder evaluates floor price | Transparently rule-based (`mode=rule_based`), not LLM |
| **Customer** | **C9. Sale Stream Flash Deals** | **PASS** | `/sale-stream` | View active flash deals feed | Live polling feed with discount badges | Sale Stream Rewind permanently cancelled/excluded |
| **Customer** | **C10. Bharat Multilingual** | **PASS** | Header Language Selector | Switch to Hindi, Tamil, Telugu, Urdu, Bengali, etc. | Interface labels translate across 12 languages (Urdu has RTL) | Core UI strings translated (~46%); catalog specs in English |
| **Customer** | **C11. Typed List to Basket** | **PASS** | `/list-to-basket` | Enter typed shopping list ("1kg Atta, 500g Ghee") | Regex/keyword parser matches catalog items into cart | Vision OCR requires external cloud vision API key |

---

## D. Step-by-Step Cross-Role Workflows

### Workflow 1 — Admin Approves Retailer
1. **Admin:** Log in as `admin@basket.demo` and navigate to `/admin/retailers`.
2. Inspect the pending retailer application (e.g. `audit.store.29835@basket.demo`).
3. Click **Approve**. The database updates `retailers.verification_status = 'APPROVED'` and logs an entry in `admin_audit_logs`.
4. **Retailer:** Open a second browser, log in as the approved retailer.
5. The retailer now has unrestricted access to `/retailer/listings` and `/retailer/inventory`.
6. **Customer:** Once the retailer publishes a listing, customers can discover and purchase it on `/products`.

### Workflow 2 — Retailer Changes Price & Customer Sees It
*(Mandatory Demonstration of State Propagation)*
1. **Retailer (Window 1):** Log in as `retailer1@basket.demo`, navigate to `/retailer/listings`.
2. Locate **"Borges Extra Virgin Cold Pressed Olive Oil 1 Litre"** (currently ₹1,099).
3. Click edit and update the price to **₹999** (99900 paise). Save changes.
4. **Backend State:** The API (`PATCH /api/v1/retailer/listings/{id}`) updates `product_listings.selling_price_paise` and appends an immutable record into `price_history_ticks`.
5. **Customer (Window 2 / Incognito):** As `customer@basket.demo`, navigate to the product page `/products/3b9e2f1c-2edc-4a21-9d82-8d944ad61967`.
6. Refresh the page (or fetch product): The product page immediately reflects the new price **₹999** along with an updated discount badge.
7. Click **Add to Cart** and proceed to `/cart`.
8. Click **Proceed to Checkout**: The server quote engine generates an HMAC-SHA256 signature calculated from the updated ₹999 price.
> **Honest Engineering Note:** The update propagates through PostgreSQL persistence and HTTP re-validation on page visit/refresh. It is deterministic server-rendered state, not a WebSocket push.

### Workflow 3 — Retailer Updates Stock & Reservation Guards
1. **Retailer:** Navigate to `/retailer/inventory`.
2. Check `on_hand_quantity` for an item (e.g. 50 units). Change it to **2 units**.
3. **Customer:** Open `/products` and add 2 units to the cart.
4. Attempt to add a 3rd unit: The UI and backend prevent it, displaying stock availability limits.
5. When the customer enters checkout, the backend creates a temporary row in `inventory_reservations` holding the 2 units for 15 minutes.
6. The retailer's dashboard now shows: `on_hand: 2, reserved: 2, available: 0`. Other customers see "Out of Stock".
7. If the customer cancels checkout, the reservation is released and available stock returns to 2.

### Workflow 4 — Retailer Creates an Offer
1. **Retailer:** Navigate to `/retailer/offers`.
2. Create an offer code (e.g., `MART15`, 15% off orders above ₹500).
3. **Customer:** Add eligible Basket Mart items to the cart.
4. Proceed to quote: The pricing engine evaluates the retailer offer against eligible items, validates the minimum order threshold, and applies the discount up to the configured cap.

### Workflow 5 — Customer Order & Retailer Fulfillment Pipeline
1. **Customer:** Place an order on `/checkout`.
2. Order is created in PostgreSQL with `status: 'CONFIRMED'` and `payment_status: 'SUCCEEDED'` (in sandbox mode).
3. **Retailer:** Open `/retailer/orders`. The new order appears under incoming orders.
4. Advance the status: Click **Mark Processing** $\rightarrow$ **Mark Packed** $\rightarrow$ **Dispatch (Shipped)** with carrier tracking details.
5. **Customer:** Open `/orders` and `/orders/[id]/track`. The delivery milestone tracker updates with timestamps.
> **Integrity Guard:** If an order has `payment_status: 'PENDING'`, attempting to advance fulfillment returns HTTP 409 `ORDER_NOT_PAID`.

### Workflow 6 — Customer RFQ & Retailer Bidding (Community Exchange)
1. **Customer:** Go to `/exchange`, click **Create Request**.
2. Request a bulk order (e.g. "50 units Cotton Bed Linen for Corporate Event", Budget ₹40,000).
3. **Retailer:** Retailer 2 (Basket Lifestyle) navigates to `/retailer/exchange`.
4. The retailer submits a competitive quote bid of ₹37,500 with delivery promise.
5. **Customer:** Views submitted bids on `/exchange`, compares offers, and clicks **Accept Bid**.
6. The accepted bid items automatically populate the customer's cart at the negotiated price.

### Workflow 7 — Dukaan vs Dukaan (Multi-Retailer Reverse Auction)
1. **Customer:** Initiate a rapid 90-second reverse auction from the cart or `/auctions`.
2. **Retailers:** Retailers stocking equivalent items submit bids lowering the price to win the order.
3. **Customer:** Watches live bid countdown; auction settles on the lowest qualified bid.
4. **Phase A Defect Fix Demonstration:** Even if the customer already has that exact listing in their cart, clicking **Accept Bid** successfully updates the cart line in place without duplicate key crashes (HTTP 500 eliminated; residual conflicts safely mapped to 409 `CART_CONFLICT`).

### Workflow 8 — Price Intelligence & Price Alerts
1. **Customer:** Open any product page with multiple retailers (e.g. Borges Olive Oil).
2. Inspect the **Price Comparison Card** showing prices across Basket Mart, Basket Lifestyle, etc.
3. Review the **90-Day Price Trend Graph** showing historical price ticks.
4. Click **Set Price Alert** (e.g. alert me when price drops below ₹1,000).
5. When a retailer lowers their price below that threshold, the customer receives an in-app price alert notification under `/account/price-alerts`.

### Workflow 9 — AI Negotiator (Rule-Based Deal Assistant)
1. **Customer:** Open `/assistant` with items in the cart.
2. Type: *"Can I get a discount on my grocery order?"*
3. The Deal Assistant evaluates the cart against retailer floor-price negotiation rules (`POST /api/v1/assistant/chat`).
4. It counters with an eligible discount offer (e.g., *"I can offer ₹50 off if you complete checkout now"*).
5. Customer clicks **Accept Deal**, and the approved discount token attaches to the checkout quote.

### Workflow 10 — Community Buying (Group Purchasing)
1. **Retailer:** Publishes a group buy deal template with volume tiers (e.g. 5 buyers unlock 20% off).
2. **Customer 1:** Starts a group purchase campaign on `/community-buying`.
3. **Customer 2 (or second browser):** Joins the group purchase campaign.
4. The progress bar updates with member initials (e.g. `C.D.`, `R.M.`).
5. Once the buyer threshold is reached, group settlement unlocks the wholesale tier price for all participants.

### Workflow 11 — Sale Stream (Flash Deals)
1. **Customer:** Open `/sale-stream`.
2. View active limited-time flash deals with countdown timers and percentage savings badges.
3. Add a flash deal directly to the basket and verify the promotional pricing at checkout.
> **Note:** Sale Stream Rewind is permanently removed; expired deals are automatically filtered out.

### Workflow 12 — List to Basket (Typed Shopping List)
1. **Customer:** Open `/list-to-basket`.
2. Type or paste a grocery list:
   ```
   1kg Basmati Rice
   500g Ghee
   1L Olive Oil
   ```
3. Click **Find Items**: The backend parser matches catalogue products and displays confidence ratings.
4. Customer reviews the matched items, adjusts quantities, and clicks **Add All to Basket**.

---

## E. 15–20 Minute Master Presentation Plan

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. ADMIN GOVERNANCE & OVERVIEW (2–3 mins)                              │
│    • Log into /admin                                                   │
│    • Show Platform Dashboard & Real-Time KPIs                          │
│    • Review Retailer KYC Moderation (/admin/retailers)                 │
│    • Show Demand Gap Analytics & Unmet localized demand (/admin/demand)│
├────────────────────────────────────────────────────────────────────────┤
│ 2. RETAILER OPERATIONS & INVENTORY (4–5 mins)                          │
│    • Log into /retailer                                                │
│    • Show Listings Management (/retailer/listings)                     │
│    • Demonstrate Stock & Available Quantity (/retailer/inventory)       │
│    • Show Order Fulfillment Workflow (/retailer/orders)                │
│    • Show Community Bidding & Reverse Auctions (/retailer/auctions)    │
├────────────────────────────────────────────────────────────────────────┤
│ 3. CUSTOMER QUICK-COMMERCE EXPERIENCE (5–6 mins)                       │
│    • Open Storefront / and /products                                   │
│    • Search & Filter across Groceries, Fashion, Electronics, Beauty    │
│    • Demonstrate Product Passport (ingredients & origin transparency)  │
│    • Show 90-Day Price Intelligence & Price Alerts                     │
│    • Demonstrate Typed List to Basket (/list-to-basket)                │
│    • Demonstrate Bharat Multilingual Language Switcher (12 languages)  │
├────────────────────────────────────────────────────────────────────────┤
│ 4. CROSS-ROLE INTERACTION DEMONSTRATIONS (4–5 mins)                    │
│    • Workflow 2: Retailer changes price → Customer sees updated price  │
│    • Workflow 5: Customer orders → Retailer fulfills packed/shipped    │
│    • Workflow 7: Dukaan vs Dukaan live reverse kirana auction          │
├────────────────────────────────────────────────────────────────────────┤
│ 5. VERSION 2 PHASE A RESILIENCE HIGHLIGHTS (2 mins)                    │
│    • Auction / Cart Conflict Resolution (0 duplicate crashes)          │
│    • Payment Idempotency (re-pressing Pay reuses pending order)        │
│    • Search Fallback (seamless PostgreSQL fallback when unconfigured)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## F. Top 10 Strongest Verified Features to Demonstrate

1. **Multi-Role RBAC & Authenticated Portals:** Complete role separation between Admin (`/admin`), Retailer (`/retailer`), and Customer (`/`) with strict shopper-only checkout enforcement.
2. **Dynamic Price Intelligence & Historical Trends:** 90-day price trend visualization, competitor price comparisons, and customer in-app price alerts.
3. **Multi-Stage Retailer Order Fulfillment Pipeline:** Full state machine (`PAID` $\rightarrow$ `CONFIRMED` $\rightarrow$ `PACKED` $\rightarrow$ `SHIPPED` $\rightarrow$ `DELIVERED`) with strict payment verification guards.
4. **Dukaan vs Dukaan (Multi-Retailer Bidding):** 90-second reverse kirana auction with Phase A cart conflict protection.
5. **Basket Community Buying:** Volume-tiered group purchasing with privacy-safe member initials and stock-safe settlement.
6. **Community Exchange (Customer RFQs):** Customer custom quote requests and competitive retailer price bidding.
7. **Demand Gap & Unmet Demand Aggregator:** Category- and pincode-level aggregation of zero-result searches and out-of-stock demand.
8. **Typed List to Basket:** Unstructured text list parsing and catalogue product matching.
9. **Bharat Multilingual Architecture:** UI localization support across 12 Indian regional languages with RTL layout support for Urdu.
10. **Transactional Outbox & Cryptographic HMAC Quotes:** Enterprise resilience with tamper-proof HMAC-SHA256 checkout quote signing and PostgreSQL search fallback.
