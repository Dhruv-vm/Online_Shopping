# BASKET — Phase 2 Architecture Specification
## Core Commerce Engine: Identity, Persistent Cart, Authoritative Pricing, Inventory Reservations, Orders, and Verified Payments

> **Document Version:** 2.0.0 (Final Approved Design)  
> **Status:** APPROVED FOR IMPLEMENTATION  
> **Repository Target:** `/PHASE_2_ARCHITECTURE.md`  
> **Scope:** Complete architecture and design for Phase 2 vertical slices (2A through 2G). No application code or migrations are modified in this step.

---

## 1. System Topology & Core Invariants

Phase 2 builds the core transactional commerce engine within BASKET’s FastAPI modular monolith, using Aiven PostgreSQL as the sole system of record. External payment provider interactions (Razorpay Sandbox) are strictly decoupled from long-running PostgreSQL transactions. Multi-item inventory reservations are protected by deterministic row locking to prevent deadlocks and overselling. All financial values are modeled in integer minor units (paise).

```text
+---------------------------------------------------------------------------------------------------------+
|                                       NEXT.JS 15 STOREFRONT (Frontend)                                  |
|   - /cart (Drawer & Full Page)  - /checkout (Address, Delivery, Summary)  - Razorpay Modal  - /orders   |
+----------------------------------------------------+----------------------------------------------------+
                                                     | HTTPS / JSON (Idempotency-Key: UUID)
                                                     v
+---------------------------------------------------------------------------------------------------------+
|                                      FASTAPI MODULAR MONOLITH (Backend)                                 |
|                                                                                                         |
|   [2A Identity]   --->  [2B Cart]   --->   [2C Pricing & Quotes]   --->   [2D Reservations]             |
|   Argon2id + JWT        Guest/User         Paise + GST HSN Engine         Lock Ordering + TTL           |
|                                                     |                                                   |
|                                                     v                                                   |
|                                            [2E Orders & Outbox]                                         |
|                                            Local DB Tx 1: Order PENDING_PAYMENT + Active Reservation   |
|                                                     |                                                   |
|                                                     v (Decoupled, Outside DB Transaction)               |
|                                            [2F Razorpay Adapter]                                        |
|                                            Creates Provider Order via HTTPS                             |
|                                                     |                                                   |
|                                                     v                                                   |
|                                            [2F Verification / Webhook / Reconciler]                     |
|                                            Local DB Tx 2: Multi-Factor Check -> Order CONFIRMED        |
+----------------------------------------------------+----------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|                                      AIVEN POSTGRESQL (System of Record)                                |
|   - users, user_sessions, addresses       - checkout_quotes, quote_items      - outbox_events (Phase 2) |
|   - carts, cart_items                     - orders, order_items, history      - Kafka Pub/Sub (Phase 3) |
|   - product_listings, store_inventory     - payments, idempotency_records                               |
+---------------------------------------------------------------------------------------------------------+
```

### Non-Negotiable Invariants
1. **Integer Paise Everywhere:** Zero floating-point arithmetic for currency. All monetary values are 64-bit integer paise (`BigInteger`, e.g., ₹28,990.00 = `2899000` paise).
2. **PostgreSQL as System of Record:** Frontend prices, tax estimates, delivery fees, and inventory numbers are completely untrusted. All calculations are executed server-side against PostgreSQL tables.
3. **Decoupled Gateway Boundaries:** External HTTPS calls to Razorpay occur strictly **outside** PostgreSQL transactions. Database connections are never held open during gateway latency.
4. **Deterministic Race Resolution:** Expiry and confirmation state transitions use conditional `UPDATE ... WHERE status = 'ACTIVE'` with row locks, eliminating double-consumption and overselling.
5. **No Release on Ambiguity:** Inventory is **never** released merely because a gateway request timed out. Uncertain payments transition to `REQUIRES_RECONCILIATION` until resolved by background reconciliation.
6. **Phase 2 / Phase 3 Event Boundary:** In Phase 2, domain events are written atomically to `outbox_events` in PostgreSQL. Kafka producers, cluster connections, topic definitions, and consumers remain in Phase 3.

---

## 2. Phase 1 Database Compatibility & Foreign Key Alignment

All new Phase 2 entities link strictly to verified Phase 1 database tables and types. No assumed schemas or columns are used:

| Phase 1 Table | Primary Key | Relevant Columns Linked in Phase 2 |
|---|---|---|
| `retailers` | `id` (CHAR(32)/UUID) | `name`, `slug`, `rating`, `is_active` |
| `categories` | `id` (CHAR(32)/UUID) | `name`, `slug`, `parent_id`, `is_active` |
| `products` | `id` (CHAR(32)/UUID) | `category_id`, `name`, `slug`, `brand`, `is_active` |
| `product_variants`| `id` (CHAR(32)/UUID) | `product_id`, `name`, `sku`, `attributes` (JSONB) |
| `product_listings`| `id` (CHAR(32)/UUID) | `retailer_id`, `variant_id`, `selling_price_paise`, `original_price_paise`, `currency`, `is_active` |
| `store_inventory` | `id` (CHAR(32)/UUID) | `listing_id` (FK to `product_listings.id`), `on_hand_quantity`, `reserved_quantity` |

---

## 3. Domain 2A: Customer Identity, Authentication & Address Management

### 3.1 Authentication Lifecycle & Security Controls
1. **Email Normalization:** All emails are stripped and lowercased before hashing or querying (`email = email.strip().lower()`).
2. **Password Hashing:** `Argon2id` via `passlib[argon2]` (memory cost: 64MB, time cost: 3 iterations, parallelism: 4).
3. **JWT Algorithm & Key Management:**
   - Algorithm: `HS256` (HMAC with SHA-256) utilizing a minimum 256-bit cryptographically random secret `settings.JWT_SECRET_KEY`.
   - Token Type Separation: Explicit `token_use` claim (`access` vs `refresh`) preventing token substitution attacks.
4. **Refresh Token Rotation & Revocation:**
   - Refresh tokens are stored as SHA-256 hashes in `user_sessions`.
   - Each token belongs to a `family_id` (UUID).
   - Upon refresh, the presented token is revoked (`is_revoked = TRUE`), and a new refresh token in the same family is issued.
   - **Reuse Detection:** If an already-revoked refresh token is presented, the entire `family_id` is immediately invalidated, terminating all associated active sessions (anti-theft protection).
5. **Session Invalidation:**
   - `POST /api/v1/auth/logout`: Revokes the current session token.
   - `POST /api/v1/auth/logout-all`: Sets `is_revoked = TRUE` across all active sessions for `user_id`.
6. **Cookie Security:**
   - `access_token` cookie: `HttpOnly=True`, `Secure=True` (in production), `SameSite="Lax"`, `Path="/api/v1"`, `Max-Age=900` (15 minutes).
   - `refresh_token` cookie: `HttpOnly=True`, `Secure=True`, `SameSite="Strict"`, `Path="/api/v1/auth"`, `Max-Age=604800` (7 days).
7. **CSRF Protection:**
   - Double-submit CSRF cookie pattern (`XSRF-TOKEN` cookie readable by JavaScript, validated against `X-CSRF-Token` header on state-mutating requests `POST`, `PATCH`, `DELETE`).
8. **Login Rate Limiting:**
   - Maximum 5 consecutive failed login attempts per `(IP, normalized_email)` per 60 seconds; 15-minute temporary lockout on 10 failures. Returns `429 Too Many Requests`.

### 3.2 Address Management & Default Address Constraints
- **At Most One Default Address (Requirement 4):** Enforced at the database engine level via PostgreSQL partial unique index:
  ```sql
  CREATE UNIQUE INDEX uq_user_default_address ON addresses (user_id) WHERE is_default = TRUE;
  ```
- **Zero-Address Behavior:** A new customer has 0 addresses and 0 default addresses.
- **First-Address Behavior:** When a user creates their first address, the service automatically forces `is_default = TRUE`.
- **Switching Default Address:** In a database transaction, setting an address to `is_default = TRUE` clears `is_default = FALSE` on all other addresses belonging to that `user_id` before committing.
- **Deletion Behavior:** If the default address is deleted:
  - If other addresses exist, the oldest remaining address (`ORDER BY created_at ASC LIMIT 1`) is automatically promoted to `is_default = TRUE`.
  - If no other addresses exist, the user returns to the zero-address state cleanly.

### 3.3 Database Schema: Identity & Addresses
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(15),
    full_name VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    role VARCHAR(32) NOT NULL DEFAULT 'customer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(64) NOT NULL UNIQUE,
    family_id UUID NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    user_agent VARCHAR(512),
    ip_address VARCHAR(45),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE addresses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_name VARCHAR(255) NOT NULL,
    phone VARCHAR(15) NOT NULL,
    line1 VARCHAR(255) NOT NULL,
    line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    landmark VARCHAR(255),
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_indian_postal_code CHECK (length(postal_code) = 6)
);

CREATE UNIQUE INDEX uq_user_default_address ON addresses (user_id) WHERE is_default = TRUE;
CREATE INDEX ix_addresses_user_id ON addresses(user_id);
CREATE INDEX ix_user_sessions_lookup ON user_sessions(refresh_token_hash) WHERE is_revoked = FALSE;
```

---

## 4. Domain 2B: Persistent Shopping Cart & Guest Migration

### 4.1 Cart Ownership & Constraints
A shopping cart belongs to either an authenticated customer (`user_id`) or an anonymous guest session (`session_id`). This mutual exclusivity is enforced via database constraint:

```sql
CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_cart_ownership CHECK (
        (user_id IS NOT NULL AND session_id IS NULL) OR 
        (user_id IS NULL AND session_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_cart_user_id ON carts(user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX uq_cart_session_id ON carts(session_id) WHERE session_id IS NOT NULL;

CREATE TABLE cart_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    listing_id UUID NOT NULL REFERENCES product_listings(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cart_listing UNIQUE (cart_id, listing_id),
    CONSTRAINT chk_cart_item_quantity CHECK (quantity > 0 AND quantity <= 10)
);

CREATE INDEX ix_cart_items_cart_id ON cart_items(cart_id);
```

### 4.2 Guest Cart Migration Workflow
When an unauthenticated guest logs in:
1. Server receives `basket_cart_session` cookie alongside valid credentials.
2. Inside an atomic PostgreSQL transaction:
   - Locks the user's permanent cart: `SELECT id FROM carts WHERE user_id = :user_id FOR UPDATE`.
   - Locates guest cart items: `SELECT listing_id, quantity FROM cart_items WHERE cart_id = :guest_cart_id`.
   - For matching items: `user_item.quantity = LEAST(user_item.quantity + guest_item.quantity, 10)`.
   - For non-matching items: re-assigns `cart_id = user_cart.id`.
   - Deletes the guest `carts` row (cascading any orphaned rows).
3. The response instructs the client to clear the `basket_cart_session` cookie.

### 4.3 Inventory Availability vs. Reservation Boundary
Cart operations in Domain 2B only perform read-only inspection of live stock availability (`max(0, on_hand_quantity - reserved_quantity)`). Cart items do not reserve inventory or mutate `store_inventory.reserved_quantity`. Formal multi-item inventory reservations, deterministic lock ordering by `listing_id`, and overselling protection are strictly scoped to Domain 2D (Inventory Reservations & Concurrency Locks).

---

## 5. Domain 2C: Configurable Indian GST & Persistent Quotes

### 5.1 Listing-Level Tax Classification & Dual GST Model
Rather than assuming a flat 18% tax, every product listing carries an official Indian Harmonized System of Nomenclature (HSN) code and an explicit GST tax bracket in basis points (`100 basis points = 1%`):

```sql
-- Configurable tax classification added to product_listings
ALTER TABLE product_listings 
ADD COLUMN hsn_code VARCHAR(16) NOT NULL DEFAULT '8518',
ADD COLUMN gst_rate_basis_points INTEGER NOT NULL DEFAULT 1800; -- 18.00%
```

#### Tax Computation Rules
Indian B2C retail requires **GST-inclusive display prices**. The pricing engine extracts the tax components mathematically:
$$\text{Base Amount Paise} = \text{round}\left(\frac{\text{Selling Price Paise} \times 10000}{10000 + \text{gst\_rate\_basis\_points}}\right)$$
$$\text{Total Tax Paise} = \text{Selling Price Paise} - \text{Base Amount Paise}$$

#### Intra-State vs Inter-State GST Rules
- Let Retailer Warehouse State = `retailer_state` (e.g., `"KA"` for Croma Bangalore).
- Let Customer Delivery State = `delivery_state` (from delivery address snapshot).
- **Intra-State (`retailer_state == delivery_state`):**
  $$\text{CGST Paise} = \text{round}\left(\frac{\text{Total Tax Paise}}{2}\right), \quad \text{SGST Paise} = \text{Total Tax Paise} - \text{CGST Paise}, \quad \text{IGST Paise} = 0$$
- **Inter-State (`retailer_state != delivery_state`):**
  $$\text{IGST Paise} = \text{Total Tax Paise}, \quad \text{CGST Paise} = 0, \quad \text{SGST Paise} = 0$$

### 5.2 Unambiguous Retailer Delivery Fee Rules
Delivery fees are calculated strictly per retailer:
- **Free Delivery Threshold:** If a customer orders $\ge$ **₹499.00 (49,900 paise)** from a retailer, delivery from that retailer is **₹0**.
- **Standard Delivery Fee:** If a customer orders $<$ **₹499.00 (49,900 paise)** from a retailer, delivery fee is **₹49.00 (4,900 paise)** for that retailer.
- Total Order Delivery Fee = Sum of all retailer delivery fees.

### 5.3 Persistent Checkout Quotes Schema
Quotes snapshot exact item prices, tax breakdowns, and delivery fees. A quote is valid for **15 minutes** and can be consumed **at most once**:

```sql
CREATE TYPE quote_status AS ENUM ('ACTIVE', 'CONSUMED', 'EXPIRED');

CREATE TABLE checkout_quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delivery_address_id UUID NOT NULL REFERENCES addresses(id) ON DELETE RESTRICT,
    subtotal_paise BIGINT NOT NULL CHECK (subtotal_paise >= 0),
    delivery_fee_paise BIGINT NOT NULL DEFAULT 0 CHECK (delivery_fee_paise >= 0),
    cgst_paise BIGINT NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
    sgst_paise BIGINT NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
    igst_paise BIGINT NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
    total_tax_paise BIGINT NOT NULL DEFAULT 0 CHECK (total_tax_paise >= 0),
    total_payable_paise BIGINT NOT NULL CHECK (total_payable_paise >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status quote_status NOT NULL DEFAULT 'ACTIVE',
    is_consumed BOOLEAN NOT NULL DEFAULT FALSE,
    consumed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE checkout_quote_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES checkout_quotes(id) ON DELETE CASCADE,
    listing_id UUID NOT NULL REFERENCES product_listings(id) ON DELETE RESTRICT,
    retailer_id UUID NOT NULL REFERENCES retailers(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_base_price_paise BIGINT NOT NULL,
    unit_selling_price_paise BIGINT NOT NULL,
    total_selling_price_paise BIGINT NOT NULL,
    cgst_paise BIGINT NOT NULL DEFAULT 0,
    sgst_paise BIGINT NOT NULL DEFAULT 0,
    igst_paise BIGINT NOT NULL DEFAULT 0,
    total_tax_paise BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_quotes_user_active ON checkout_quotes(user_id, status) WHERE status = 'ACTIVE';
```

---

## 6. Domain 2D: High-Concurrency Inventory Reservations & Race Handling (Implemented)

### 6.1 Deadlock-Free Lock Ordering
To eliminate PostgreSQL transaction deadlocks during concurrent multi-item checkouts, inventory rows are always locked in **lexicographical ascending order of `listing_id`**:

```python
# Guaranteed deadlock elimination via deterministic lock ordering
sorted_listing_ids = sorted(set(item.listing_id for item in quote.items))

stmt = (
    select(StoreInventory)
    .where(StoreInventory.listing_id.in_(sorted_listing_ids))
    .with_for_update()  # Acquires row-level write lock
    .order_by(StoreInventory.listing_id.asc())
)
inventories = {
    inv.listing_id: inv
    for inv in (await session.execute(stmt)).scalars().all()
}

# Verify availability for all items before any mutation (All-or-Nothing)
shortages = []
for item in quote.items:
    inv = inventories.get(item.listing_id)
    if not inv or (inv.on_hand_quantity - inv.reserved_quantity) < item.quantity:
        shortages.append(item)
if shortages:
    raise AppException(code="INSUFFICIENT_STOCK", status_code=409, details=shortages)

for item in quote.items:
    inventories[item.listing_id].reserved_quantity += item.quantity
```

### 6.2 Reservation State Machine & Expiry vs. Payment Race
Reservations are governed by the `inventory_reservations` and `inventory_reservation_items` tables (`0006_inventory_reservations`) with a configurable TTL (`settings.RESERVATION_TTL_MINUTES`, default 10 minutes):

```sql
CREATE TABLE inventory_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES users(id) ON DELETE CASCADE,
    guest_token_hash VARCHAR(64),
    quote_id UUID NOT NULL REFERENCES checkout_quotes(id) ON DELETE RESTRICT,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    idempotency_key VARCHAR(128),
    expires_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,
    release_reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_reservation_ownership CHECK (
        (customer_id IS NOT NULL AND guest_token_hash IS NULL) OR
        (customer_id IS NULL AND guest_token_hash IS NOT NULL)
    ),
    CONSTRAINT chk_reservation_status CHECK (
        status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')
    )
);

CREATE TABLE inventory_reservation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reservation_id UUID NOT NULL REFERENCES inventory_reservations(id) ON DELETE CASCADE,
    listing_id UUID NOT NULL REFERENCES product_listings(id) ON DELETE RESTRICT,
    retailer_id UUID NOT NULL REFERENCES retailers(id) ON DELETE RESTRICT,
    variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_reservation_listing UNIQUE (reservation_id, listing_id)
);
```

#### Deterministic Race Resolution Protocol
When an authorized order confirmation request (Phase 2E) and the background cleanup worker collide:
1. Both processes execute `SELECT ... FROM inventory_reservations WHERE id = :id FOR UPDATE`.
2. **If Confirmation wins lock:** Status is `ACTIVE`. The confirming transaction sets `status = 'CONFIRMED'`, converts reserved stock to permanent sale (`on_hand -= qty, reserved -= qty`), and commits. The expiry worker subsequently sees `CONFIRMED` and skips.
3. **If Expiry Worker wins lock:** Expiry worker decrements `reserved_quantity`, sets `status = 'EXPIRED'`, sets `released_at = NOW()`, and commits.
   - When Confirmation runs next, it discovers `status == 'EXPIRED'` and rejects confirmation with `409 RESERVATION_EXPIRED`. Stock is never deducted twice and cannot become negative.

### 6.3 Idempotency Semantics, Database Agreement & Retry Policy

The reservation system enforces strict idempotency at both the PostgreSQL constraint layer and the service layer:

1. **Database Constraint Architecture:**
   - `uq_reservations_customer_idempotency`: `UNIQUE(customer_id, idempotency_key) WHERE customer_id IS NOT NULL AND idempotency_key IS NOT NULL`.
   - `uq_reservations_guest_idempotency`: `UNIQUE(guest_token_hash, idempotency_key) WHERE guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL`.
   - `uq_reservations_quote_active`: `UNIQUE(quote_id) WHERE status = 'ACTIVE'`.
2. **Service Idempotency Matrix:**
   - **Repeated Request with Same Key & Same Quote (Active/Confirmed):** Returns cached reservation with HTTP 201. Idempotent safe replay.
   - **Cross-Quote Replay:** Replaying a previously used idempotency key with a *different* quote ID is rejected with `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`.
   - **Spent Key Replay:** If an idempotency key was previously associated with a reservation that is now `RELEASED` or `EXPIRED`, the service immediately rejects with `409 IDEMPOTENCY_KEY_ALREADY_USED`. It will **never** silently allocate a fresh reservation under a replayed idempotency key.
   - **Retry Policy After Release or Expiry:** If a quote's reservation expired or was voluntarily released, the customer must submit a request with a **fresh idempotency key**.
   - **Concurrent Identical Keys:** Two simultaneous requests with identical keys are serialized by the PostgreSQL unique index. The winner inserts the reservation; the losing transaction catches `IntegrityError`, rolls back, retrieves the winning reservation, and returns it cleanly (HTTP 201).
   - **Concurrent Different Keys for Same Quote:** Two simultaneous requests with different keys for the same quote are serialized by `uq_reservations_quote_active`. The winner creates the active reservation; the second transaction catches `IntegrityError`, rolls back, retrieves the existing active reservation for the quote, and returns it cleanly. Inventory is held exactly once.

### 6.4 Internal Service Key Security Architecture

The cleanup endpoint (`POST /api/v1/internal/reservations/cleanup-expired`) is reserved for internal cron jobs and administrative orchestrators:
1. **Zero Default Secret in Production:** `INTERNAL_SERVICE_KEY: SecretStr | None = None`. In production (`ENVIRONMENT == "production"`), the application fails to boot if `INTERNAL_SERVICE_KEY` is not explicitly configured, if it is shorter than 32 characters, or if it uses weak/predictable patterns (e.g. `password`, `changeme`, `secret`).
2. **Fail-Closed Authorization:** If `INTERNAL_SERVICE_KEY` is not set on the server, all requests to internal endpoints are immediately rejected with `401 UNAUTHORIZED`. Missing server configuration cannot disable authentication.
3. **Constant-Time Comparison:** Inbound keys from headers (`X-Internal-Service-Key` or `X-Internal-Token`) are compared against the configured secret using `hmac.compare_digest` to prevent timing attacks.
4. **Credential Isolation:** The internal service key is strictly isolated from customer/guest auth tokens, is never stored in browser cookies or localStorage, and is never exposed in API response payloads or client bundles.

---

## 7. Domain 2E: Order Creation, Reservation Confirmation, Outbox & Quote Consumption

> [!IMPORTANT]
> **Strict Phase 2E / Phase 2F Separation Boundary:**
> - **Phase 2E Scope:** Validates active unexpired Quote and active Reservation, creates the authoritative `Order` and `OrderItems` records, calls `ReservationService.confirm_reservation(...)` to atomically convert reserved stock into on-hand deductions, marks the Quote consumed, and writes the `order.created` event to `outbox_events`. All of this runs inside a single, local atomic PostgreSQL transaction. **No external Razorpay API calls, payment capture, or payment verification occur in Phase 2E.**
> - **Phase 2F Scope:** Introduces the decoupled Razorpay payment lifecycle: initiating provider orders via external HTTPS (`razorpay_client.order.create`), client signature verification, payment webhooks (`order.paid`), payment failure recovery, background reconciliation, and automated refunds.

### 7.1 Phase 2E Atomic Transaction Flow
```text
[Customer submits Checkout / Place Order with (quote_id, reservation_id, idempotency_key)]
                                    |
                                    v
==================== SINGLE ATOMIC LOCAL POSTGRESQL TRANSACTION (< 25ms) ====================
1. Check customer idempotency record (customer_id, idempotency_key). If completed, return cached order.
2. Select and lock active CheckoutQuote:
   - Verify quote is not consumed (`quote.is_consumed == False`).
   - Verify quote has not expired (`quote.expires_at > NOW()`).
3. Select and lock active InventoryReservation:
   - Verify reservation belongs to customer/guest.
   - Verify reservation is `ACTIVE` and unexpired (`expires_at > NOW()`).
   - Verify reservation `quote_id == quote.id`.
4. Confirm Reservation (via ReservationService.confirm_reservation, internal=True):
   - Atomically decrement `on_hand_quantity -= qty` and `reserved_quantity -= qty` across listings.
   - Set reservation status = 'CONFIRMED', confirmed_at = NOW().
5. Insert Order and OrderItems rows:
   - Snapshot delivery address, retailer breakdowns, line items, and statutory GST splits.
   - Set order.status = 'PENDING' (or 'PENDING_PAYMENT').
6. Consume Quote:
   - Set quote.is_consumed = True, quote.status = 'CONSUMED'.
7. Insert Transactional Outbox Event:
   - Insert row into outbox_events with topic 'order.created' and serialized OrderCreatedPayload.
COMMIT TRANSACTION
=============================================================================================
```

### 7.2 Orders Schema & Strict Scoped Idempotency
```sql
CREATE TYPE order_status AS ENUM (
    'PENDING_PAYMENT',
    'CONFIRMED',
    'PAYMENT_FAILED',
    'CANCELLED',
    'SHIPPED',
    'DELIVERED'
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(32) UNIQUE NOT NULL, -- e.g. BSK-20261116-A8F2
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    quote_id UUID UNIQUE NOT NULL REFERENCES checkout_quotes(id) ON DELETE RESTRICT,
    delivery_address_snapshot JSONB NOT NULL,
    subtotal_paise BIGINT NOT NULL CHECK (subtotal_paise >= 0),
    delivery_fee_paise BIGINT NOT NULL DEFAULT 0 CHECK (delivery_fee_paise >= 0),
    cgst_paise BIGINT NOT NULL DEFAULT 0 CHECK (cgst_paise >= 0),
    sgst_paise BIGINT NOT NULL DEFAULT 0 CHECK (sgst_paise >= 0),
    igst_paise BIGINT NOT NULL DEFAULT 0 CHECK (igst_paise >= 0),
    total_tax_paise BIGINT NOT NULL DEFAULT 0 CHECK (total_tax_paise >= 0),
    total_amount_paise BIGINT NOT NULL CHECK (total_amount_paise >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status order_status NOT NULL DEFAULT 'PENDING_PAYMENT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    listing_id UUID NOT NULL REFERENCES product_listings(id) ON DELETE RESTRICT,
    retailer_id UUID NOT NULL REFERENCES retailers(id) ON DELETE RESTRICT,
    product_title VARCHAR(255) NOT NULL,
    variant_name VARCHAR(255) NOT NULL,
    seller_name VARCHAR(255) NOT NULL,
    hsn_code VARCHAR(16) NOT NULL,
    unit_base_price_paise BIGINT NOT NULL,
    unit_selling_price_paise BIGINT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_price_paise BIGINT NOT NULL CHECK (total_price_paise >= 0),
    cgst_paise BIGINT NOT NULL DEFAULT 0,
    sgst_paise BIGINT NOT NULL DEFAULT 0,
    igst_paise BIGINT NOT NULL DEFAULT 0,
    total_tax_paise BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE order_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    from_status order_status,
    to_status order_status NOT NULL,
    reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Requirement 7: Scoped Idempotency Table
CREATE TABLE idempotency_records (
    key VARCHAR(128) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_hash VARCHAR(64) NOT NULL,
    status_code INTEGER,
    response_body JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    PRIMARY KEY (user_id, key)
);
```

---

## 8. Domain 2F: Razorpay Payments, Server-Side Verification & Crash Recovery

### 8.1 Hardened Payment Verification Pipeline
When the frontend invokes `POST /api/v1/payments/verify`:
1. **Cryptographic HMAC Check:** Constant-time comparison of `hmac_sha256(order_id + "|" + payment_id, secret)` against `razorpay_signature`.
2. **Authoritative Provider Fetch:** Query Razorpay API directly: `rzp_payment = razorpay_client.payment.fetch(payment_id)`.
3. **Multi-Factor Validation (Zero Trust on Client):**
   - Assert `rzp_payment["order_id"] == payment.provider_order_id`.
   - Assert `rzp_payment["amount"] == order.total_amount_paise`.
   - Assert `rzp_payment["currency"] == "INR"`.
   - Assert `rzp_payment["status"] in ("captured", "authorized")`.
   - Assert `payment.user_id == current_user.id`.
4. **Single Successful Payment Rule (Requirement 7):** Enforced by database constraint:
```sql
CREATE TYPE payment_status AS ENUM (
    'INITIATED',
    'SUCCESS',
    'FAILED',
    'REFUNDED',
    'REQUIRES_RECONCILIATION'
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL DEFAULT 'RAZORPAY_SANDBOX',
    provider_order_id VARCHAR(128) NOT NULL,
    provider_payment_id VARCHAR(128) UNIQUE,
    provider_signature VARCHAR(255),
    amount_paise BIGINT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status payment_status NOT NULL DEFAULT 'INITIATED',
    error_code VARCHAR(64),
    error_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Exactly one SUCCESSFUL payment allowed per order
CREATE UNIQUE INDEX uq_order_successful_payment 
ON payments (order_id) 
WHERE status = 'SUCCESS';

CREATE INDEX ix_payments_provider_order ON payments(provider_order_id);
```

### 8.2 Raw Request Body Webhook Verification
FastAPI Pydantic parsers modify whitespace and dictionary keys, breaking signature validation. The webhook route reads raw bytes directly:

```python
@router.post("/payments/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Annotated[str, Header()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    raw_body: bytes = await request.body()  # Untouched raw binary payload

    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, x_razorpay_signature):
        raise AppException(
            code="INVALID_WEBHOOK_SIGNATURE",
            message="Tampered webhook payload",
            status_code=400,
        )

    event_payload = json.loads(raw_body.decode("utf-8"))
    # Process event idempotently...
```

### 8.3 Crash Recovery & Background Reconciler (`PaymentReconciliationWorker`)
- **Server Crashes during Gateway Call:** If the server restarts after DB Transaction 1, the order remains in `PENDING_PAYMENT`. When the customer re-submits checkout with the same `Idempotency-Key`, the service safely resumes and generates the payment intent.
- **Reconciliation Worker:** Runs every 5 minutes. Scans orders stuck in `PENDING_PAYMENT` or payments in `REQUIRES_RECONCILIATION`:
  - Queries `razorpay_client.order.fetchPayments(provider_order_id)`.
  - If payment is `captured`, marks `payment -> SUCCESS` and `order -> CONFIRMED`.
  - If no payment exists and reservation is expired, releases inventory and marks `order -> CANCELLED`.

---

## 9. Transactional Outbox Table (Phase 2 Boundary)

Domain events are persisted in PostgreSQL within the business transaction. Kafka publishing remains deferred to Phase 3:

```sql
CREATE TABLE outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(64) NOT NULL, -- 'order', 'payment', 'inventory'
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(64) NOT NULL,     -- 'order.created', 'order.paid', 'order.cancelled'
    payload JSONB NOT NULL,
    published_at TIMESTAMPTZ,            -- NULL in Phase 2; published by Phase 3 worker
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_outbox_unpublished ON outbox_events(created_at) WHERE published_at IS NULL;
```

---

## 10. Frontend Storefront Architecture

### 10.1 Routes & Components
```text
frontend/
  ├── app/
  │   ├── cart/page.tsx               # Full-page cart with multi-retailer breakdown
  │   ├── checkout/page.tsx           # Multi-step checkout with address selection & sticky quote
  │   ├── orders/
  │   │   ├── page.tsx                # Customer order history list
  │   │   └── [id]/page.tsx           # Detailed order confirmation & item tracking
  ├── components/
  │   ├── cart/
  │   │   ├── cart-drawer.tsx         # Slide-over quick cart drawer
  │   │   ├── cart-item-card.tsx      # Quantity stepper, item price, retailer badge
  │   │   └── delivery-threshold.tsx  # Dynamic indicator: "Add ₹199 for FREE Delivery from Croma"
  │   ├── checkout/
  │   │   ├── address-selector.tsx    # Default address card + modal address manager
  │   │   ├── quote-timer.tsx         # Visual 15-minute countdown clock
  │   │   └── razorpay-modal.tsx      # Next.js dynamic script loader and handler
```

---

## 11. Automated Testing Strategy

1. **Authentication Tests (`backend/tests/test_auth.py`):**
   - Argon2id password verification, JWT cookie setting/parsing, email normalization.
   - Refresh token rotation, reuse detection (family invalidation).
   - Rate limiting: assert 429 on 6th failed attempt.
   - Guest cart migration: anonymous cart consolidated into user cart on login.
2. **Pricing & Taxes Tests (`backend/tests/test_pricing.py`):**
   - Integer paise calculations across HSN brackets (0%, 5%, 12%, 18%, 28%).
   - Intra-state CGST + SGST split vs Inter-state IGST calculation.
   - Delivery fee thresholds: ₹0 fee for $\ge$ ₹499; ₹49 for $<$ ₹499 per retailer.
3. **Quotes Tests (`backend/tests/test_quotes.py`):**
   - Immutable snapshot creation, 15-minute expiration, single-use consumption constraint.
4. **Concurrency & Oversell Tests (`backend/tests/test_concurrency.py`):**
   - 30 concurrent checkout workers competing for 3 units using `asyncio.gather`.
   - Assert: Exactly 3 succeed; 27 receive `INSUFFICIENT_STOCK`. Zero negative inventory.
5. **Deterministic Race Tests (`backend/tests/test_expiry_race.py`):**
   - Verification vs Expiry worker lock contention resolution.
6. **Payment & Signature Tests (`backend/tests/test_payments.py`):**
   - Valid HMAC signature succeeds; tampered signature fails with 400.
   - Raw binary webhook verification passes.
   - `REQUIRES_RECONCILIATION` state transition tested on simulated gateway timeout.
   - Duplicate payment on confirmed order blocked by `uq_order_successful_payment`.

---

## 12. Single-Developer Implementation Sequence

```
[2A: Identity & Addresses]
           |
           v
[2B: Persistent Cart Domain]
           |
           v
[2C: Pricing, Taxes & Persistent Quotes]
           |
           v
[2D: Inventory Reservations & Concurrency Locks]
           |
           v
[2E: Orders, Outbox & Checkout Orchestration]
           |
           v
[2F: Razorpay Payments, Webhooks & Recovery Worker]
           |
           v
[2G: Storefront UI, End-to-End Verification & Gate Script]
```

| Slice | Focus | Definition of Done |
|---|---|---|
| **2A** | Identity, Auth & Addresses | `User`, `UserSession`, `Address` models, Argon2id, JWT cookies, rate limiter, address partial index. Pytest passes. |
| **2B** | Persistent Cart Domain | `Cart`, `CartItem` models, ownership check constraints, guest migration service. Cart CRUD tests pass. |
| **2C** | Pricing, Taxes & Quotes | HSN tax calculation (CGST/SGST/IGST), delivery threshold logic, `CheckoutQuote` model. Pricing tests pass. |
| **2D** | Inventory Reservations | Lock ordering (`listing_id`), `InventoryReservation` model, 30-worker concurrency tests with 0 oversell. |
| **2E** | Orders & Checkout | `Order`, `OrderItem`, `IdempotencyRecord`, `OutboxEvent` models, decoupled transaction 1 & 2. |
| **2F** | Payments & Recovery | Decoupled Razorpay adapter, multi-factor validation, raw webhook handler, reconciler worker, expiry race. |
| **2G** | Storefront UI & E2E Testing | Cart drawer/page, address manager, checkout stepper, Razorpay modal, order tracking, `verify-environment.sh` exits 0. |

---

## 13. Summary of Documentation Files Changed

1. `PHASE_2_ARCHITECTURE.md`: Created final complete Phase 2 architecture specification.
2. `AGENT_HANDOFF.md`: Appended dated handoff entry recording the final architecture review and approval.
