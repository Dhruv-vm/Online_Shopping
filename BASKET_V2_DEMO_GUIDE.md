# BASKET — Version 2.0 Product Demonstration Runbook

This guide provides a structured, role-by-role demonstration walkthrough for showcasing BASKET Version 2.0 to stakeholders, investors, and product teams.

---

## 1. Demo Credentials Reference

All demonstration accounts share the standard password: `Basket@123`

| Role | Email | Starting URL | Primary Capabilities |
| :--- | :--- | :--- | :--- |
| **Customer** | `customer@basket.demo` | `/` or `/account` | Browse, Search, Basket, Quotes, Intent, Missions, Checkout |
| **Retailer 1** | `retailer1@basket.demo` | `/retailer` | Inventory, Listings, Orders, Dukaan vs Dukaan Bidding, RFQs |
| **Retailer 2** | `retailer2@basket.demo` | `/retailer` | Competing Store, Reverse Auction Counter-Bidding |
| **Admin** | `admin@basket.demo` | `/admin` | Governance, Retailer Approvals, Catalogue, Deals, Demand Gap |

---

## 2. End-to-End Demonstration Walkthrough

### Scenario A: Customer Shopping Intent & Demand Gap Generation
1. Log in as `customer@basket.demo` and navigate to **Account → Shopping Intent** (`/account/intent`).
2. Input shopping requirements:
   - Name: `Weekly Essentials`
   - PIN Code: `560034`
   - Budget: `₹2,500`
   - Items: `Rice` (1x), `Ghee` (1x), `Handcrafted Ceramic Teapot` (1x).
3. Click **Save Intent**:
   - The system displays what it understood.
   - For `Rice` and `Ghee`: Matches verified local stores serving PIN 560034 with sufficient stock.
   - For `Handcrafted Ceramic Teapot`: If out of local inventory, automatically registers a **Demand Gap** signal in the demand pool.
4. Click **Create Basket**: Available items are immediately added to the shopping basket with optimal unit pricing.

---

### Scenario B: Dynamic Coupon Validation in Basket
1. Navigate to the **Shopping Basket** (`/cart`).
2. Review items and observe the dynamic Quote breakdown (Delivery Charges, GST calculation, Total Payable).
3. In the Order Summary card, locate the **Apply Coupon** input:
   - Try an invalid code (e.g. `INVALID99`): Displays clear error badge without breaking the cart.
   - Enter a valid platform code: Quote re-evaluates immediately via `POST /api/v1/quotes` and subtracts the discount from the total payable amount.
4. Refresh the page: The applied coupon remains stored and persisted for the active session.

---

### Scenario C: Stock Reservation & Checkout with Razorpay Test Mode
1. From `/cart`, click **Proceed to Checkout** (`/checkout`).
2. Select a saved delivery address.
3. Observe that stock is locked via a 10-minute temporary inventory reservation (`POST /api/v1/reservations`).
4. Click **Confirm Order & Proceed to Payment**:
   - Razorpay Modal / Hosted Checkout opens in Test Mode.
   - Complete payment with a test bank or mock card.
   - Order transitions to `CONFIRMED` upon signature verification.

---

### Scenario D: Dukaan vs Dukaan (Retailer Live Reverse Auction)
1. Open a second browser session / incognito window and log in as `retailer1@basket.demo`.
2. Navigate to **Retailer Console → Auctions** (`/retailer/auctions`).
3. View active auctions in the retailer's service PIN:
   - See your current rank and competing store counts.
   - View the anonymized price ladder (competitor identities masked).
   - Enter a counter-bid to undercut the lowest offer.
4. Observe the live countdown timer. When the auction closes, the system executes an atomic update, notifying the winning retailer and customer.

---

### Scenario E: Real-Time Notifications & SSE Synchronisation
1. Observe the notification bell in the top navigation bar.
2. When actions occur (new RFQ posted, auction concluded, order placed), notifications stream into the header in real-time via Server-Sent Events (`lib/realtime.ts`).
3. Portals update quietly in the background without full-page flickers or manual refreshes.

---

### Scenario F: Admin Platform Governance & Moderation
1. Log in as `admin@basket.demo` and navigate to `/admin`.
2. Open **Retailer Approvals**: Review pending store KYC submissions and approve verified merchants.
3. Open **Demand Gap Analytics**: Inspect unmet consumer demand aggregated across PIN codes to recruit targeted retail supply.
4. Open **Audit Logs**: Inspect immutable, actor-correlated logs of all administrative actions.
