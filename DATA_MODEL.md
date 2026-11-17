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
