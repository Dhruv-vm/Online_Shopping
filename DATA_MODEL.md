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
