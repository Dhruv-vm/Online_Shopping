# BASKET — Data Model and Ownership

This is the initial logical model, not a command to create every table immediately. Implement only the tables needed for the current vertical slice. Use Alembic migrations and coordinate migration ownership.

## 1. Core entities

### Identity and retail
- `users` — customer/admin identities and status.
- `retailers` — retailer organizations.
- `stores` — physical or fulfilment locations.
- `user_roles` / role assignments — authorization mapping.

### Catalogue
- `products` — canonical product identity and approved attributes.
- `product_variants` — size, pack, colour, model, and other variant attributes.
- `categories` — hierarchical category structure.
- `retailer_listings` — retailer-specific listing, SKU, listing status.
- `prices` — price history/current price, currency, validity/freshness metadata.
- `store_inventory` — available and reserved quantity per listing/store.
- `raw_products` — untrusted ingestion staging records, if ingestion is implemented.
- `product_reviews` — review decisions, reviewer, reason, timestamps.
- `catalogue_sync_logs` — source sync outcomes and errors.

### Commerce
- `carts`, `cart_items`
- `orders`, `order_items`
- `inventory_reservations`, `reservation_items`
- `payments`
- `idempotency_records` (or equivalent durable idempotency mechanism)

### Eventing
- `outbox_events`
- `processed_events` (or consumer-specific idempotency table)

## 2. Important relationships

- One retailer has many stores and listings.
- One canonical product may have multiple variants.
- A retailer listing references one exact product variant.
- Inventory is scoped to a listing/store combination.
- A cart item references a specific listing/variant and requested quantity.
- An order contains immutable item snapshots: title/variant, unit price, quantity, currency, seller/store reference.
- Reservations belong to a checkout/order attempt and contain item-level quantities.
- Payment records reference an order and provider reference, with verified status transitions.
- Outbox events are linked to an aggregate type and aggregate ID.

## 3. Data invariants

- Use UUID primary keys unless an established repository convention says otherwise.
- Store money as integer minor units and currency code.
- Store timestamps in UTC.
- Add foreign keys and appropriate unique constraints.
- Add indexes for common lookup and join paths.
- Prevent negative inventory with database constraints and atomic updates.
- Keep order item price/title snapshots even if catalogue data changes later.
- Track provenance and freshness for externally sourced catalogue data.
- Never use fuzzy product-name matching to combine distinct variants.

## 4. Inventory model

At minimum distinguish:
- `on_hand_quantity`
- `reserved_quantity`
- `available_quantity = on_hand_quantity - reserved_quantity`

The database must prevent negative available quantity under concurrent checkouts. Implement atomic conditional updates or row-level locking in a transaction. Do not calculate availability only in frontend code.

## 5. Reservation lifecycle

Suggested states:
- `ACTIVE`
- `CONFIRMED`
- `RELEASED`
- `EXPIRED`

Transitions must be explicit and idempotent. A reservation should be confirmed or released once. Expiry processing must not release already confirmed reservations.

## 6. Order lifecycle

Keep the initial state machine small and explicit, for example:
- `PENDING_PAYMENT`
- `CONFIRMED`
- `PAYMENT_FAILED`
- `CANCELLED`

Add fulfilment states only if the demo requires them. Validate transitions in backend service logic.

## 7. Migration discipline

- One designated migration owner at a time.
- Never edit an already-applied migration to change history.
- Never create multiple Alembic heads unintentionally.
- Before merging a migration, run migration upgrade from a clean database and test downgrade where practical.
- Record schema changes in `AGENT_HANDOFF.md` and the PR.

## 8. Phase 2B Cart Schema Specification (Implemented)

### `carts` Table
- `id`: UUID (PK, default `uuid.uuid4`)
- `customer_id`: UUID (FK `users.id` ON DELETE CASCADE, nullable)
- `guest_token_hash`: VARCHAR(64) (SHA-256 hex digest of 256-bit entropy token, nullable, unique)
- `status`: VARCHAR(32) (Default `'ACTIVE'`, Check: `status IN ('ACTIVE', 'MERGED', 'ABANDONED', 'CONVERTED')`)
- `currency`: VARCHAR(3) (Default `'INR'`)
- `version`: INTEGER (Default 1)
- `expires_at`: TIMESTAMPTZ (Nullable, 30 days for guest carts)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_cart_ownership`: `(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR (customer_id IS NULL AND guest_token_hash IS NOT NULL)`
  - `uq_cart_customer_active`: Partial unique index on `(customer_id, currency)` WHERE `customer_id IS NOT NULL AND status = 'ACTIVE'`
  - Indexes on `customer_id`, `guest_token_hash`, `status`, `expires_at`.

### `cart_items` Table
- `id`: UUID (PK, default `uuid.uuid4`)
- `cart_id`: UUID (FK `carts.id` ON DELETE CASCADE, indexed)
- `listing_id`: UUID (FK `product_listings.id` ON DELETE RESTRICT, indexed)
- `variant_id`: UUID (FK `product_variants.id` ON DELETE RESTRICT, indexed)
- `retailer_id`: UUID (FK `retailers.id` ON DELETE RESTRICT, indexed)
- `quantity`: INTEGER (Check: `quantity > 0 AND quantity <= 10`, default 1)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `uq_cart_listing`: Unique index on `(cart_id, listing_id)`
  - `chk_cart_item_quantity`: Quantity between 1 and 10 inclusive.

### Dynamic Pricing & Stock Policy
- Cart items do not store price or subtotal columns.
- All monetary totals (unit price, item subtotal, cart subtotal) are derived dynamically at query time from catalogue listings (`ProductListing.selling_price_paise * quantity`).
- Live inventory availability is calculated dynamically as `max(0, on_hand_quantity - reserved_quantity)`.
- If an item's listing is deactivated or inventory is insufficient, the item remains visible in the cart with `is_available: false` and informative validation banners, blocking checkout until resolved.
- **Phase Boundary Clarification**: In Phase 2B, cart operations validate available quantity via read-only inspection of `store_inventory`. Cart additions and updates do not reserve inventory or mutate `store_inventory.reserved_quantity`. Multi-item inventory reservations with deterministic lock ordering (`listing_id`) and reservation TTL belong to Phase 2D (Inventory Reservations & Concurrency Protection).

## 9. Phase 2C Pricing Engine, GST & Persistent Quotes Schema Specification (Implemented)

### Catalogue Additions (`0005_pricing_quotes_schema`)
- `retailers.state`: VARCHAR(100) (Default `'KA'`, nullable=False) — Retailer origin state used for intra-state vs inter-state GST determination.
- `product_listings.hsn_code`: VARCHAR(16) (Default `'8518'`, nullable=False) — Statutory Indian Harmonized System of Nomenclature code.
- `product_listings.gst_rate_basis_points`: INTEGER (Default `1800`, nullable=False) — Statutory GST rate in basis points (`1800 = 18.00%`).

### `discounts` Table
- `id`: UUID (PK, default `uuid.uuid4`)
- `listing_id`: UUID (FK `product_listings.id` ON DELETE CASCADE, indexed)
- `discount_type`: VARCHAR(32) (`PERCENTAGE` or `FIXED_AMOUNT`, Check: `discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')`)
- `discount_value`: INTEGER (Check: `discount_value > 0`) — Basis points for percentage (e.g. 1000 = 10%) or minor paise for fixed amount.
- `max_discount_paise`: INTEGER (Nullable, Check: `max_discount_paise IS NULL OR max_discount_paise > 0`) — Optional cap for percentage discounts.
- `valid_from`: TIMESTAMPTZ (Default `now()`)
- `valid_until`: TIMESTAMPTZ (Nullable)
- `is_active`: BOOLEAN (Default `True`)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- `updated_at`: TIMESTAMPTZ (Default `now()`)

### `checkout_quotes` Table
- `id`: UUID (PK, default `uuid.uuid4`)
- `customer_id`: UUID (FK `users.id` ON DELETE CASCADE, nullable)
- `session_id`: VARCHAR(64) (Nullable, SHA-256 hash of guest token)
- `cart_id`: UUID (FK `carts.id` ON DELETE SET NULL, nullable, indexed)
- `delivery_address_id`: UUID (FK `addresses.id` ON DELETE SET NULL, nullable, indexed)
- `delivery_state`: VARCHAR(100) (Nullable, e.g. `'KA'`)
- `subtotal_paise`: BIGINT (Check: `>= 0`)
- `discount_total_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `delivery_fee_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `cgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `sgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `igst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_tax_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_payable_paise`: BIGINT (Check: `>= 0`)
- `currency`: VARCHAR(3) (Default `'INR'`)
- `status`: VARCHAR(32) (Default `'ACTIVE'`, Check: `status IN ('ACTIVE', 'CONSUMED', 'EXPIRED', 'SUPERSEDED')`)
- `is_consumed`: BOOLEAN (Default `False`)
- `consumed_at`: TIMESTAMPTZ (Nullable)
- `expires_at`: TIMESTAMPTZ (15-minute guarantee from creation)
- `superseded_by_quote_id`: UUID (FK `checkout_quotes.id` ON DELETE SET NULL, nullable)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_quote_ownership`: `(customer_id IS NOT NULL AND session_id IS NULL) OR (customer_id IS NULL AND session_id IS NOT NULL)`
  - Partial index `ix_quotes_customer_active` on `(customer_id, status)` WHERE `status = 'ACTIVE' AND customer_id IS NOT NULL`
  - Partial index `ix_quotes_guest_active` on `(session_id, status)` WHERE `status = 'ACTIVE' AND session_id IS NOT NULL`

### `checkout_quote_items` Table
- `id`: UUID (PK, default `uuid.uuid4`)
- `quote_id`: UUID (FK `checkout_quotes.id` ON DELETE CASCADE, indexed)
- `listing_id`: UUID (FK `product_listings.id` ON DELETE RESTRICT, indexed)
- `variant_id`: UUID (FK `product_variants.id` ON DELETE RESTRICT, indexed)
- `retailer_id`: UUID (FK `retailers.id` ON DELETE RESTRICT, indexed)
- `product_title`: VARCHAR(255) (Immutable snapshot)
- `variant_title`: VARCHAR(255) (Immutable snapshot)
- `sku`: VARCHAR(100) (Nullable)
- `hsn_code`: VARCHAR(16)
- `gst_rate_basis_points`: INTEGER
- `quantity`: INTEGER (Check: `quantity > 0`)
- `unit_original_price_paise`: BIGINT (Check: `>= 0`)
- `unit_selling_price_paise`: BIGINT (Check: `>= 0`)
- `unit_discount_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `unit_discounted_price_paise`: BIGINT (Check: `>= 0`)
- `total_selling_price_paise`: BIGINT (Check: `>= 0`)
- `taxable_base_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `cgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `sgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `igst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_tax_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `retailer_name`: VARCHAR(255) (Immutable snapshot)
- `retailer_state`: VARCHAR(100) (Immutable snapshot)
- `created_at`: TIMESTAMPTZ (Default `now()`)

## 10. Phase 2D Inventory Reservations & Concurrency Protection Schema Specification (Implemented)

### `inventory_reservations` Table (`0006_inventory_reservations`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `customer_id`: UUID (FK `users.id` ON DELETE CASCADE, nullable, indexed)
- `guest_token_hash`: VARCHAR(64) (Nullable, SHA-256 hash of `basket_guest_cart` cookie, indexed)
- `quote_id`: UUID (FK `checkout_quotes.id` ON DELETE RESTRICT, nullable=False, indexed)
- `status`: VARCHAR(32) (Default `'ACTIVE'`, Check: `status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')`, indexed)
- `idempotency_key`: VARCHAR(128) (Nullable, indexed)
- `expires_at`: TIMESTAMPTZ (Configurable TTL, default 10 minutes from creation, indexed)
- `confirmed_at`: TIMESTAMPTZ (Nullable, set when transitioning to `CONFIRMED`)
- `released_at`: TIMESTAMPTZ (Nullable, set when transitioning to `RELEASED` or `EXPIRED`)
- `release_reason`: VARCHAR(255) (Nullable, e.g. `'USER_RELEASED'`, `'TTL_EXPIRED'`)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_reservation_ownership`: `(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR (customer_id IS NULL AND guest_token_hash IS NOT NULL)`
  - Partial unique index `uq_reservations_quote_active` on `(quote_id)` WHERE `status = 'ACTIVE'`
  - Partial unique index `uq_reservations_customer_idempotency` on `(customer_id, idempotency_key)` WHERE `customer_id IS NOT NULL AND idempotency_key IS NOT NULL`
  - Partial unique index `uq_reservations_guest_idempotency` on `(guest_token_hash, idempotency_key)` WHERE `guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL`
  - Index `ix_reservations_status_expires` on `(status, expires_at)`

### `inventory_reservation_items` Table (`0006_inventory_reservations`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `reservation_id`: UUID (FK `inventory_reservations.id` ON DELETE CASCADE, nullable=False, indexed)
- `listing_id`: UUID (FK `product_listings.id` ON DELETE RESTRICT, nullable=False, indexed)
- `retailer_id`: UUID (FK `retailers.id` ON DELETE RESTRICT, nullable=False, indexed)
- `variant_id`: UUID (FK `product_variants.id` ON DELETE RESTRICT, nullable=False, indexed)
- `quantity`: INTEGER (Check: `quantity > 0`)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_reservation_item_quantity_positive`: `quantity > 0`
  - `uq_reservation_listing`: UNIQUE on `(reservation_id, listing_id)`

## 11. Phase 2E Orders, Outbox & Idempotency Schema Specification (Implemented)

### `orders` Table (`0007_orders_outbox_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `order_number`: VARCHAR(64) (UNIQUE, indexed, format: `BSK-YYYYMMDD-XXXXXX`)
- `customer_id`: UUID (FK `users.id` ON DELETE SET NULL, nullable, indexed)
- `guest_token_hash`: VARCHAR(64) (Nullable, SHA-256 hash of guest session, indexed)
- `quote_id`: UUID (FK `checkout_quotes.id` ON DELETE RESTRICT, nullable=False, UNIQUE, indexed)
- `reservation_id`: UUID (FK `inventory_reservations.id` ON DELETE RESTRICT, nullable=False, indexed)
- `delivery_address_snapshot`: JSONB (Immutable snapshot of recipient name, address lines, city, state, postal code, phone)
- `subtotal_paise`: BIGINT (Check: `>= 0`)
- `discount_total_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `delivery_fee_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `cgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `sgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `igst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_tax_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_payable_paise`: BIGINT (Check: `>= 0`)
- `currency`: VARCHAR(3) (Default `'INR'`)
- `status`: VARCHAR(32) (Default `'PENDING_PAYMENT'`, Check: `status IN ('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED')`, indexed)
- `payment_status`: VARCHAR(32) (Default `'NOT_INITIATED'`, Check: `payment_status IN ('NOT_INITIATED', 'PENDING', 'PAID', 'FAILED', 'REFUNDED')`, indexed)
- `idempotency_key`: VARCHAR(128) (Nullable, indexed)
- `payment_window_expires_at`: TIMESTAMPTZ (Nullable, indexed, default 15 minutes hold)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_order_ownership`: `(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR (customer_id IS NULL AND guest_token_hash IS NOT NULL)`
  - `chk_order_tax_reconciliation`: `cgst_paise + sgst_paise + igst_paise = total_tax_paise`
  - `chk_order_payable_reconciliation`: `subtotal_paise - discount_total_paise + delivery_fee_paise + total_tax_paise = total_payable_paise`
  - `uq_orders_quote_id`: UNIQUE on `(quote_id)`
  - Index `ix_orders_customer_created`: `(customer_id, created_at DESC)`
  - Index `ix_orders_guest_created`: `(guest_token_hash, created_at DESC)`
  - Index `ix_orders_status_payment_window`: `(status, payment_window_expires_at)`

### `order_items` Table (`0007_orders_outbox_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `order_id`: UUID (FK `orders.id` ON DELETE CASCADE, nullable=False, indexed)
- `listing_id`: UUID (FK `product_listings.id` ON DELETE RESTRICT, nullable=False, indexed)
- `variant_id`: UUID (FK `product_variants.id` ON DELETE RESTRICT, nullable=False, indexed)
- `retailer_id`: UUID (FK `retailers.id` ON DELETE RESTRICT, nullable=False, indexed)
- `product_title`: VARCHAR(255) (Immutable snapshot)
- `variant_title`: VARCHAR(255) (Nullable, immutable snapshot)
- `sku`: VARCHAR(100) (Nullable, immutable snapshot)
- `hsn_code`: VARCHAR(20) (Nullable, immutable snapshot)
- `gst_rate_basis_points`: INTEGER (Check: `>= 0`)
- `quantity`: INTEGER (Check: `quantity > 0`)
- `unit_original_price_paise`: BIGINT (Check: `>= 0`)
- `unit_selling_price_paise`: BIGINT (Check: `>= 0`)
- `unit_discount_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `unit_discounted_price_paise`: BIGINT (Check: `>= 0`)
- `total_selling_price_paise`: BIGINT (Check: `>= 0`)
- `taxable_base_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `cgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `sgst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `igst_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `total_tax_paise`: BIGINT (Default `0`, Check: `>= 0`)
- `retailer_name`: VARCHAR(255) (Immutable snapshot)
- `retailer_state`: VARCHAR(100) (Immutable snapshot)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_order_item_tax_reconciliation`: `cgst_paise + sgst_paise + igst_paise = total_tax_paise`
  - `chk_order_item_base_reconciliation`: `taxable_base_paise + total_tax_paise = total_selling_price_paise`
  - `uq_order_item_listing`: UNIQUE on `(order_id, listing_id)`

### `order_status_history` Table (`0007_orders_outbox_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `order_id`: UUID (FK `orders.id` ON DELETE CASCADE, nullable=False, indexed)
- `from_status`: VARCHAR(32) (Nullable)
- `to_status`: VARCHAR(32) (Nullable=False)
- `reason`: VARCHAR(255) (Nullable)
- `metadata`: JSONB (Default `{}`)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)

### `outbox_events` Table (`0007_orders_outbox_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `aggregate_type`: VARCHAR(64) (Nullable=False, indexed, e.g. `'order'`)
- `aggregate_id`: UUID (Nullable=False, indexed)
- `event_type`: VARCHAR(128) (Nullable=False, indexed, e.g. `'order.created'`)
- `schema_version`: INTEGER (Default `1`)
- `payload`: JSONB (Zero-PII event payload, containing financial breakdown, item summary, and non-PII IDs)
- `status`: VARCHAR(32) (Default `'PENDING'`, Check: `status IN ('PENDING', 'PUBLISHED', 'FAILED')`, indexed)
- `retry_count`: INTEGER (Default `0`, Check: `>= 0`)
- `last_error`: TEXT (Nullable)
- `published_at`: TIMESTAMPTZ (Nullable)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Indexes**:
  - `ix_outbox_status_created`: `(status, created_at)`

### `idempotency_records` Table (`0007_orders_outbox_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `scope`: VARCHAR(64) (Nullable=False, indexed, e.g. `'order_placement'`)
- `customer_id`: UUID (FK `users.id` ON DELETE CASCADE, nullable, indexed)
- `guest_token_hash`: VARCHAR(64) (Nullable, indexed)
- `idempotency_key`: VARCHAR(128) (Nullable=False, indexed)
- `request_hash`: VARCHAR(64) (Nullable=False, SHA-256 canonical hash of payload)
- `order_id`: UUID (FK `orders.id` ON DELETE SET NULL, nullable, indexed)
- `response_payload`: JSONB (Nullable)
- `expires_at`: TIMESTAMPTZ (Nullable=False, indexed, 24-hour TTL)
- `created_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - Partial unique index `uq_idempotency_customer`: `(scope, customer_id, idempotency_key)` WHERE `customer_id IS NOT NULL`
  - Partial unique index `uq_idempotency_guest`: `(scope, guest_token_hash, idempotency_key)` WHERE `guest_token_hash IS NOT NULL`
  - Index `ix_idempotency_expires`: `(expires_at)`

### `inventory_reservations` Table Alterations (`0007_orders_outbox_schema`)
- Added column `order_id`: UUID (FK `orders.id` ON DELETE SET NULL, nullable, indexed)
- Updated status check constraint to include `'ALLOCATED_TO_ORDER'`:
  `status IN ('ACTIVE', 'ALLOCATED_TO_ORDER', 'CONFIRMED', 'RELEASED', 'EXPIRED')`

---

## 12. Phase 2F — Payments, Capture Ledger, Multi-Refund & Webhook Schema (`0008_payments_razorpay_schema`)

### `payments` Table (Payment Attempts — `0008_payments_razorpay_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `order_id`: UUID (FK `orders.id` ON DELETE RESTRICT, nullable=False, indexed)
- `customer_id`: UUID (FK `users.id` ON DELETE RESTRICT, nullable, indexed)
  *(Enforces unified financial retention: financial records are immutable; customer account deletion is handled by soft-deletion/anonymization in users without deleting user rows)*
- `guest_token_hash`: VARCHAR(64) (Nullable, indexed)
- `provider`: VARCHAR(32) (Default `'RAZORPAY_SANDBOX'`, nullable=False)
- `provider_order_id`: VARCHAR(128) (Nullable during `CREATING`, indexed)
- `provider_payment_id`: VARCHAR(128) (Nullable, initial payment attempt reference)
- `idempotency_key`: VARCHAR(128) (Nullable=False)
- `attempt_number`: INTEGER (Default `1`, nullable=False)
- `amount_paise`: BIGINT (Nullable=False, check `>= 0`)
- `currency`: VARCHAR(3) (Default `'INR'`, nullable=False)
- `status`: VARCHAR(32) (Default `'CREATING'`, check: `status IN ('CREATING', 'CREATION_AMBIGUOUS', 'PENDING', 'AUTHORIZED', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')`, indexed)
- `method`: VARCHAR(32) (Nullable, e.g. `'card'`, `'upi'`, `'netbanking'`)
- `error_code`: VARCHAR(64) (Nullable)
- `error_description`: TEXT (Nullable)
- `metadata`: JSONB (Default `{}`)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `chk_payment_ownership`: Check `(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR (customer_id IS NULL AND guest_token_hash IS NOT NULL)`
  - `uq_payments_order_idempotency`: UNIQUE `(order_id, idempotency_key)`
  - `uq_payments_order_attempt`: UNIQUE `(order_id, attempt_number)`
  - `uq_payments_id_order`: UNIQUE `(id, order_id)` (Target for composite foreign keys)

### `payment_captures` Table (Durable Capture Ledger — `0008_payments_razorpay_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `payment_id`: UUID (FK `payments.id` ON DELETE RESTRICT, nullable=False, indexed)
- `order_id`: UUID (FK `orders.id` ON DELETE RESTRICT, nullable=False, indexed)
- `provider`: VARCHAR(32) (Default `'RAZORPAY_SANDBOX'`, nullable=False)
- `provider_payment_id`: VARCHAR(128) (Nullable=False, unique `pay_xxx` from gateway)
- `provider_order_id`: VARCHAR(128) (Nullable)
- `amount_paise`: BIGINT (Nullable=False, check `> 0`)
- `currency`: VARCHAR(3) (Default `'INR'`, nullable=False)
- `status`: VARCHAR(32) (Default `'CAPTURED'`, nullable=False)
- `method`: VARCHAR(32) (Nullable)
- `acquirer_reference`: VARCHAR(128) (Nullable, bank RRN / ARN / UPI ref)
- `is_fulfillment_eligible`: BOOLEAN (Default `FALSE`, nullable=False)
- `reconciliation_status`: VARCHAR(32) (Default `'NORMAL'`, check: `reconciliation_status IN ('NORMAL', 'OVERPAYMENT_ANOMALY', 'PARTIAL_CAPTURE_REJECTED', 'LATE_CAPTURE_ANOMALY', 'RESOLVED')`, indexed)
- `captured_at`: TIMESTAMPTZ (Nullable=False)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `uq_payment_captures_provider_payment`: UNIQUE on `(provider, provider_payment_id)` (Exactly-once provider capture recording)
  - `uq_payment_captures_id_order`: UNIQUE on `(id, order_id)` (Composite key for order linkage)
  - `fk_payment_captures_payment_same_order`: FOREIGN KEY `(payment_id, order_id)` REFERENCES `payments(id, order_id)` ON DELETE RESTRICT
- **Triggers**:
  - `trg_payment_captures_protect_immutable`: BEFORE UPDATE OR DELETE ON `payment_captures`. Disallows `DELETE` completely. Disallows `UPDATE` of core immutable financial facts and historical eligibility: `provider`, `provider_payment_id`, `order_id`, `payment_id`, `amount_paise`, `currency`, `captured_at`, and `is_fulfillment_eligible`.

### `orders` Table Alterations (`0008_payments_razorpay_schema`)
- Added column `fulfilling_capture_id`: UUID (UNIQUE, nullable) — Single authoritative source of truth for fulfillment
- Added composite foreign key:
  `CONSTRAINT fk_orders_fulfilling_capture_same_order FOREIGN KEY (fulfilling_capture_id, id) REFERENCES payment_captures(id, order_id) ON DELETE RESTRICT`
  *(Enforces strictly at database level that an order can only be fulfilled by a capture belonging to that exact same order)*
- Updated check constraint `chk_order_payment_status` to include `'PARTIALLY_REFUNDED'`:
  `payment_status IN ('NOT_INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')`
- **Triggers**:
  - `trg_orders_fulfilling_capture_immutable`: BEFORE INSERT OR UPDATE ON `orders`. Enforces:
    1. On INSERT: if `fulfilling_capture_id` is non-null, validates that the capture exists for this order and has `is_fulfillment_eligible = TRUE`.
    2. On UPDATE: once `fulfilling_capture_id` is set, it cannot be modified to a different capture ID.
    3. On UPDATE: once `fulfilling_capture_id` is set, it cannot be cleared (set back to NULL).
    4. On UPDATE: when newly assigning `fulfilling_capture_id`, validates that the capture exists for this order and has `is_fulfillment_eligible = TRUE`.

### `payment_refunds` Table (`0008_payments_razorpay_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `capture_id`: UUID (FK `payment_captures.id` ON DELETE RESTRICT, nullable=False, indexed)
- `payment_id`: UUID (FK `payments.id` ON DELETE RESTRICT, nullable=False, indexed)
- `order_id`: UUID (FK `orders.id` ON DELETE RESTRICT, nullable=False, indexed)
- `provider_refund_id`: VARCHAR(128) (Unique, nullable)
- `idempotency_key`: VARCHAR(128) (Unique, nullable=False)
- `amount_paise`: BIGINT (Nullable=False, check `> 0`)
- `currency`: VARCHAR(3) (Default `'INR'`, nullable=False)
- `status`: VARCHAR(32) (Default `'REFUND_REQUESTED'`, check: `status IN ('REFUND_REQUESTED', 'REFUND_PENDING', 'REFUND_PROCESSED', 'REFUND_FAILED')`, indexed)
- `reason`: VARCHAR(255) (Nullable)
- `error_code`: VARCHAR(64) (Nullable)
- `error_description`: TEXT (Nullable)
- `metadata`: JSONB (Default `{}`)
- `processed_at`: TIMESTAMPTZ (Nullable)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `fk_refunds_capture_same_order`: FOREIGN KEY `(capture_id, order_id)` REFERENCES `payment_captures(id, order_id)` ON DELETE RESTRICT
  - `fk_refunds_payment_same_order`: FOREIGN KEY `(payment_id, order_id)` REFERENCES `payments(id, order_id)` ON DELETE RESTRICT

### `webhook_events` Table (`0008_payments_razorpay_schema`)
- `id`: UUID (PK, default `uuid.uuid4`)
- `provider`: VARCHAR(32) (Default `'RAZORPAY'`, nullable=False)
- `provider_event_id`: VARCHAR(128) (Nullable=False, populated from `x-razorpay-event-id` header)
- `event_type`: VARCHAR(128) (Nullable=False)
- `payload`: JSONB (Nullable=False, sensitive card/bank data scrubbed)
- `status`: VARCHAR(32) (Default `'PENDING'`, check: `status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'IGNORED', 'FAILED')`, indexed)
- `claimed_by`: VARCHAR(128) (Nullable, worker identifier holding processing lease)
- `claim_expires_at`: TIMESTAMPTZ (Nullable, lease expiration timestamp for worker crash recovery)
- `retry_count`: INTEGER (Default `0`, nullable=False)
- `error_message`: TEXT (Nullable)
- `processed_at`: TIMESTAMPTZ (Nullable)
- `created_at`: TIMESTAMPTZ (Default `now()`, indexed)
- `updated_at`: TIMESTAMPTZ (Default `now()`)
- **Constraints & Indexes**:
  - `uq_webhook_provider_event`: UNIQUE on `(provider, provider_event_id)`
  - Index `ix_webhook_claim`: `(status, claim_expires_at)`
  - Index `ix_webhook_created`: `(created_at)`

---

## 13. Phase 3 — Kafka Streaming, Outbox Leases & Consumer Inbox (`0009_outbox_lease_and_consumer_inbox`)

Authoritative Specification: `PHASE_3_ARCHITECTURE.md` (Version 2.0.0 Distributed Systems & Reliability Correction)

### `outbox_events` Table Alterations (`0009_outbox_lease_and_consumer_inbox`)
- Added column `claimed_by`: VARCHAR(128) (Nullable, worker identifier holding publishing lease)
- Added column `claim_expires_at`: TIMESTAMPTZ (Nullable, lease expiration timestamp for worker crash recovery)
- Added column `next_attempt_at`: TIMESTAMPTZ (Default `now()`, nullable=False, scheduled timestamp for durable backoff retries)
- Added column `correlation_id`: VARCHAR(128) (Nullable, trace identifier for end-to-end telemetry)
- Updated status check constraint to include `'PROCESSING'`:
  `status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED')`
- **Updated Indexes**:
  - Replaced `ix_outbox_pending` with partial index `ix_outbox_lease_poll`:
    `ON outbox_events (status, next_attempt_at, claim_expires_at) WHERE status IN ('PENDING', 'PROCESSING')`

### `consumer_inbox` Table (`0009_outbox_lease_and_consumer_inbox`)
Durable deduplication table providing effectively-once consumer side effects across crashes and at-least-once Kafka deliveries:
- `id`: UUID (PK, default `uuid.uuid4`)
- `consumer_group`: VARCHAR(128) (Nullable=False, indexed, e.g. `'basket-opensearch-sync'`)
- `event_id`: UUID (Nullable=False, indexed, references `EventEnvelope.event_id`)
- `aggregate_type`: VARCHAR(64) (Nullable=False)
- `aggregate_id`: UUID (Nullable=False)
- `processed_at`: TIMESTAMPTZ (Default `now()`, indexed)
- **Constraints & Indexes**:
  - `uq_consumer_inbox_group_event`: UNIQUE on `(consumer_group, event_id)`
  - Index `ix_consumer_inbox_retention`: `(processed_at)` (For 30-day inbox pruning)

### OpenSearch Derived Document Projection (`basket_products` Index)
*Note: Stored in OpenSearch, not PostgreSQL. Documented here for cross-system data model alignment.*
- `product_id`: Keyword (Authoritative UUID from `products.id`)
- `product_name`: Text (Search analyzer + Edge n-gram autocomplete)
- `product_slug`: Keyword
- `brand`: Text (Analyzed + raw Keyword)
- `category`: Object (`id`: Keyword, `name`: Text/Keyword, `slug`: Keyword)
- `description`: Text (Search analyzer)
- `primary_image_url`: Keyword
- `min_price_paise`: Long (Minimum selling price across active listings)
- `max_price_paise`: Long (Maximum selling price across active listings)
- `has_discount`: Boolean (Derived: `min_price_paise < max_original_price_paise`)
- `max_discount_percentage`: Float
- `is_in_stock`: Boolean (True if aggregate available inventory > 0)
- `total_available_quantity`: Integer
- `retailer_count`: Integer
- `retailers`: Array of Objects (`id`, `name`, `slug`, `selling_price_paise`, `original_price_paise`, `rating`, `is_available`)
- `is_active`: Boolean
- `created_at`, `updated_at`: Date
- `version`: Long (External versioning using monotonic epoch millisecond timestamp for `external_gte` concurrency protection)
