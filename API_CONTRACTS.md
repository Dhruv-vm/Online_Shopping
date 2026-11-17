# BASKET — API Contracts (Initial Agreement)

This document defines the initial interface boundaries. It is a contract proposal until the team validates and implements it. Do not invent extra fields independently; coordinate changes through `AGENT_HANDOFF.md`.

## 1. Conventions

- Base path: `/api/v1`
- JSON request/response bodies, UTF-8.
- Use UUIDs for externally visible entity identifiers.
- Timestamps are UTC ISO-8601.
- Money is represented as integer minor units (for INR, paise) plus an explicit currency code. Do not use floating-point values for money.
- Paginate list endpoints using `limit` and `cursor` or a consistent page/offset scheme selected during foundation.
- Return structured errors consistently.
- Never expose internal stack traces or secrets.

## 2. Standard error shape

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be processed.",
    "request_id": "uuid",
    "details": []
  }
}
```

Use stable machine-readable `code` values. Do not make frontend logic depend on human-readable message text.

## 3. Initial endpoint map

### Health
- `GET /health` — process health.
- `GET /ready` — readiness including required dependency checks, with safe status details.

### Catalogue
- `GET /api/v1/products` — browse approved products.
- `GET /api/v1/products/{product_id}` — product detail.
- `GET /api/v1/search` — product search via OpenSearch.
- `GET /api/v1/categories` — category navigation.

### Cart
- `GET /api/v1/cart` — current user's cart.
- `POST /api/v1/cart/items` — add/update an item.
- `PATCH /api/v1/cart/items/{item_id}` — change quantity.
- `DELETE /api/v1/cart/items/{item_id}` — remove item.

### Checkout and orders
- `POST /api/v1/checkout/quote` — server-side validation of cart, price, availability, and fulfilment.
- `POST /api/v1/checkout` — create order/reservations with an idempotency key.
- `GET /api/v1/orders` — current user's orders.
- `GET /api/v1/orders/{order_id}` — order detail/status.

### Payments
- `POST /api/v1/payments/{payment_id}/verify` — verify a sandbox payment result when applicable.
- Provider webhook endpoint must be separately defined and signature-verified. Do not accept a client-provided "paid=true" flag.

### Retailer/admin (minimum viable)
- `GET /api/v1/admin/review-queue` — authorized review queue if ingestion is built.
- `POST /api/v1/admin/products/{product_id}/approve` — authorized approval if ingestion is built.

## 4. Contract requirements

For every endpoint document:
- Authentication and role requirements
- Request schema
- Response schema
- Validation rules
- Error codes
- Idempotency behaviour where relevant
- Pagination/filter semantics
- Whether the result is authoritative or eventually consistent

## 5. Checkout invariants

- Client-supplied price is never authoritative.
- Checkout revalidates price and stock against PostgreSQL.
- Multi-item reservation is all-or-nothing.
- Checkout retries with the same idempotency key must not create duplicate orders.
- A payment redirect is not proof of payment.
- Order state transitions must be validated server-side.

## 6. API change process

1. Propose the change in `AGENT_HANDOFF.md`.
2. Identify frontend/backend consumers.
3. Agree on request and response schema.
4. Update this document.
5. Implement on a feature branch.
6. Add tests and update examples.
7. Include the contract change in the PR description.

## 7. Universal Shopping Cart Contracts (Phase 2B Implemented)

### `GET /api/v1/cart`
- **Auth**: Optional (Authenticated via session/bearer token or Guest via `basket_guest_cart` cookie / `X-Guest-Cart-Token` header).
- **Description**: Returns active cart with dynamically calculated prices, inventory availability, multi-retailer groupings, and warnings.
- **Response**: `CartResponse` (`200 OK`)
  ```json
  {
    "id": "uuid",
    "status": "ACTIVE",
    "currency": "INR",
    "items": [
      {
        "id": "uuid",
        "listing_id": "uuid",
        "variant_id": "uuid",
        "product_id": "uuid",
        "product_name": "String",
        "product_slug": "String",
        "variant_name": "String",
        "attributes": {},
        "primary_image_url": "String",
        "retailer_id": "uuid",
        "retailer_name": "String",
        "retailer_rating": 4.8,
        "unit_price_paise": 199900,
        "quantity": 2,
        "subtotal_paise": 399800,
        "available_stock": 10,
        "is_available": true,
        "validation_message": null,
        "created_at": "ISO-8601",
        "updated_at": "ISO-8601"
      }
    ],
    "item_count": 1,
    "total_quantity": 2,
    "subtotal_paise": 399800,
    "retailers": [
      {
        "retailer_id": "uuid",
        "retailer_name": "String",
        "item_count": 1,
        "subtotal_paise": 399800
      }
    ],
    "warnings": [],
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
  }
  ```

### `POST /api/v1/cart/items`
- **Auth**: Optional (Guest or Customer).
- **CSRF**: Enforced if authenticated via cookie.
- **Request Body**:
  ```json
  {
    "listing_id": "uuid",
    "quantity": 1
  }
  ```
- **Validation**:
  - `quantity`: 1 to 10 inclusive.
  - Cumulative item quantity in cart cannot exceed 10 (`MAX_QUANTITY_EXCEEDED`).
  - Requested quantity cannot exceed available stock (`INSUFFICIENT_STOCK`).
  - Listing, variant, product, and retailer must all be active (`ITEM_UNAVAILABLE`).
- **Response**: `CartResponse` (`200 OK`)

### `PATCH /api/v1/cart/items/{item_id}`
- **Auth**: Optional (Guest or Customer).
- **CSRF**: Enforced if authenticated via cookie.
- **Request Body**:
  ```json
  {
    "quantity": 3
  }
  ```
- **Validation**:
  - `quantity`: 1 to 10 inclusive.
  - Cannot exceed available inventory.
  - Item must belong to the active cart.
- **Response**: `CartResponse` (`200 OK`)

### `DELETE /api/v1/cart/items/{item_id}`
- **Auth**: Optional (Guest or Customer).
- **CSRF**: Enforced if authenticated via cookie.
- **Response**: `CartResponse` (`200 OK`)

### `DELETE /api/v1/cart`
- **Auth**: Optional (Guest or Customer).
- **CSRF**: Enforced if authenticated via cookie.
- **Description**: Clears all items in the active cart.
- **Response**: `CartResponse` (`200 OK`)

### `POST /api/v1/cart/merge`
- **Auth**: Required (`current_user`).
- **CSRF**: Enforced if cookie-authenticated.
- **Request Body**:
  ```json
  {
    "guest_token": "optional-string"
  }
  ```
  *(If omitted in body, resolves from `basket_guest_cart` cookie or `X-Guest-Cart-Token` header)*.
- **Description**: Atomically merges guest cart into customer cart with pessimistic locking. Duplicates combine quantities capped at `min(10, available_stock)`. Marks guest cart `MERGED` and clears `basket_guest_cart` cookie.
- **Response**: `CartMergeResponse` (`200 OK`)
  ```json
  {
    "cart": { ... },
    "migrated_items_count": 2,
    "warnings": []
  }
  ```

## 8. Pricing Engine, GST & Persistent Quotes Contracts (Phase 2C Implemented)

### `POST /api/v1/quotes` and `POST /api/v1/checkout/quote`
- **Auth**: Optional (Authenticated customer or guest cart session via cookie/header).
- **CSRF**: Enforced if authenticated via cookie.
- **Description**: Generates an authoritative pricing quote from the caller's active cart. Evaluates listing prices, active discounts, per-retailer delivery thresholds, and statutory Indian GST (CGST/SGST vs IGST). Persists immutable snapshot with a 15-minute TTL.
- **Request Body**:
  ```json
  {
    "delivery_address_id": "optional-uuid",
    "delivery_state": "optional-string"
  }
  ```
- **Response**: `QuoteResponse` (`201 Created`)
  ```json
  {
    "id": "uuid",
    "customer_id": "uuid-or-null",
    "cart_id": "uuid-or-null",
    "delivery_address_id": "uuid-or-null",
    "delivery_state": "KA",
    "subtotal_paise": 599800,
    "discount_total_paise": 0,
    "delivery_fee_paise": 0,
    "cgst_paise": 45747,
    "sgst_paise": 45747,
    "igst_paise": 0,
    "total_tax_paise": 91494,
    "total_payable_paise": 599800,
    "currency": "INR",
    "status": "ACTIVE",
    "is_consumed": false,
    "expires_at": "2026-11-17T15:00:00Z",
    "items": [
      {
        "id": "uuid",
        "listing_id": "uuid",
        "variant_id": "uuid",
        "retailer_id": "uuid",
        "product_title": "Sony WH-1000XM5 Wireless Headphones",
        "variant_title": "Black",
        "sku": "SONY-WH1000XM5-BLK",
        "hsn_code": "8518",
        "gst_rate_basis_points": 1800,
        "quantity": 1,
        "unit_original_price_paise": 2999000,
        "unit_selling_price_paise": 2999000,
        "unit_discount_paise": 0,
        "unit_discounted_price_paise": 2999000,
        "total_selling_price_paise": 2999000,
        "taxable_base_paise": 2541525,
        "cgst_paise": 228738,
        "sgst_paise": 228737,
        "igst_paise": 0,
        "total_tax_paise": 457475,
        "retailer_name": "Croma Electronics",
        "retailer_state": "KA"
      }
    ],
    "retailer_breakdowns": [
      {
        "retailer_id": "uuid",
        "retailer_name": "Croma Electronics",
        "retailer_state": "KA",
        "subtotal_paise": 2999000,
        "delivery_fee_paise": 0,
        "free_delivery_threshold_paise": 49900,
        "qualifies_for_free_delivery": true,
        "amount_needed_for_free_delivery_paise": 0
      }
    ]
  }
  ```

### `GET /api/v1/quotes/{id}`
- **Auth**: Optional (Guest or Customer; isolated by caller ownership).
- **Description**: Retrieves quote details by ID with automated expiry detection.

### `POST /api/v1/quotes/{id}/validate`
- **Auth**: Optional (Caller ownership validated).
- **CSRF**: Enforced if cookie-authenticated.
- **Description**: Re-evaluates quote items against current catalogue prices, GST tax rates, and live stock. Returns detailed issues list (`PRICE_CHANGED`, `GST_CHANGED`, `STOCK_DEFICIT`, `QUOTE_EXPIRED`).
- **Response**: `QuoteValidationResponse` (`200 OK`)

### `POST /api/v1/quotes/{id}/refresh`
- **Auth**: Optional (Caller ownership validated).
- **CSRF**: Enforced if cookie-authenticated.
- **Description**: Generates a fresh quote reflecting current catalogue state, marks the previous quote `SUPERSEDED`, and links `superseded_by_quote_id`.
- **Response**: `QuoteResponse` (`200 OK`)

### `GET /api/v1/quotes`
- **Auth**: Required (`current_user`).
- **Description**: Lists recent quotes generated by the authenticated customer.

---

## 8. Inventory Reservations & Concurrency Protection API (Phase 2D)

### `POST /api/v1/reservations`
- **Auth**: Optional (Guest via `basket_guest_cart` cookie or Customer via Bearer token).
- **Headers**:
  - `Idempotency-Key`: String (Optional, recommended for network retries).
- **Payload**:
  ```json
  {
    "quote_id": "uuid",
    "idempotency_key": "optional-client-string"
  }
  ```
- **Description**: Atomically reserves inventory across all listings in an active checkout quote using PostgreSQL `SELECT FOR UPDATE` in deterministic ascending `listing_id` order. All-or-nothing guarantee.
- **Response**: `201 Created`
  ```json
  {
    "id": "uuid",
    "quote_id": "uuid",
    "customer_id": "uuid",
    "status": "ACTIVE",
    "idempotency_key": "string",
    "expires_at": "2026-11-17T15:10:00Z",
    "seconds_remaining": 600,
    "is_expired": false,
    "items": [
      {
        "id": "uuid",
        "listing_id": "uuid",
        "retailer_id": "uuid",
        "variant_id": "uuid",
        "quantity": 2
      }
    ],
    "created_at": "2026-11-17T15:00:00Z",
    "updated_at": "2026-11-17T15:00:00Z"
  }
  ```
- **Errors**:
  - `404 QUOTE_NOT_FOUND`: Quote does not exist or caller ownership check fails.
  - `409 QUOTE_EXPIRED`: Quote validity has elapsed.
  - `409 INSUFFICIENT_STOCK`: One or more items do not have sufficient stock (returns detailed shortage array).
  - `409 IDEMPOTENCY_KEY_ALREADY_USED`: The provided idempotency key was previously associated with a reservation that is now `RELEASED` or `EXPIRED`. Replays of spent keys are rejected; client must submit a fresh idempotency key to retry.
  - `409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD`: The idempotency key was previously used for a different quote ID.
  - `409 CONCURRENT_RESERVATION_CONFLICT`: A conflicting reservation is currently being processed. Client should retry.

### `GET /api/v1/reservations/{id}`
- **Auth**: Optional (Caller ownership validated; cross-tenant or unauthenticated returns 404).
- **Description**: Fetches reservation details, line items, and remaining hold duration in seconds. Handles on-demand auto-expiry if TTL elapsed.
- **Response**: `200 OK` (Same schema as `ReservationResponse`).

### `POST /api/v1/reservations/{id}/release`
- **Auth**: Optional (Caller ownership validated).
- **Description**: Explicitly cancels an active reservation and restores reserved inventory counters back to available stock.
- **Response**: `200 OK`
  ```json
  {
    "id": "uuid",
    "status": "RELEASED",
    "released_at": "2026-11-17T15:05:00Z",
    "release_reason": "USER_RELEASED"
  }
  ```

### `POST /api/v1/internal/reservations/cleanup-expired`
- **Auth**: Internal service authorization required via header `X-Internal-Service-Key` or `X-Internal-Token`. Public customers, guests, or unauthorized callers without the valid secret key are rejected with `401 UNAUTHORIZED`. Missing server configuration fails closed.
- **Description**: Background cleanup worker endpoint that queries active reservations past TTL, acquires row locks, sets status to `EXPIRED`, and restores inventory.
- **Response**: `200 OK`
  ```json
  {
    "expired_count": 5,
    "timestamp": "2026-11-17T15:15:00Z"
  }
  ```

---

## 9. Order Creation & Outbox Integration (Phase 2E)

### `POST /api/v1/orders`
- **Auth**: Required (`current_user` or validated checkout guest session cookie/token).
- **Headers**:
  - `Idempotency-Key`: String (Optional in header or request body).
- **Payload**:
  ```json
  {
    "quote_id": "uuid",
    "reservation_id": "uuid",
    "delivery_address_id": "uuid | null",
    "delivery_address": {
      "full_name": "Rahul Verma",
      "address_line1": "123 Indiranagar 100ft Road",
      "address_line2": "Apt 4B",
      "city": "Bengaluru",
      "state": "Karnataka",
      "postal_code": "560038",
      "phone": "+919876543210"
    },
    "idempotency_key": "string | null"
  }
  ```
- **Description**: Executes within a single atomic local PostgreSQL transaction:
  1. Validates unconsumed and unexpired active `quote_id`.
  2. Validates active, unexpired `reservation_id` matching the quote.
  3. Transitions reservation status to `ALLOCATED_TO_ORDER` and links `reservation.order_id = order.id`, protecting inventory holds from ordinary cleanup during the 15-minute payment window. Permanent deduction (`on_hand -= qty, reserved -= qty`) is deferred to Phase 2F upon confirmed payment.
  4. Snapshots delivery address, category line items, and statutory GST splits into `orders` and `order_items` tables with initial status `PENDING_PAYMENT` and `payment_status = 'NOT_INITIATED'`.
  5. Marks `quote.is_consumed = TRUE` and `quote.status = 'CONSUMED'`.
  6. Reconciles cart selectively: removes or decrements only items included in the ordered quote, preserving unquoted cart items.
  7. Writes zero-PII `order.created` event into `outbox_events` table for downstream asynchronous messaging.
  8. Records scoped idempotency record in `idempotency_records` with canonical SHA-256 request fingerprint.
- **Exclusions (Phase 2E)**: No external Razorpay gateway requests, payment capture, or payment webhooks occur in Phase 2E. Those belong strictly to Phase 2F.
- **Response**: `201 Created` (`OrderResponse`).

### `GET /api/v1/orders`
- **Auth**: Required (`current_user` or validated guest session).
- **Query Parameters**:
  - `limit`: Integer (Default 20, max 100).
  - `offset`: Integer (Default 0).
- **Description**: Lists paginated orders belonging strictly to the calling customer or guest.
- **Response**: `200 OK`
  ```json
  {
    "orders": [
      {
        "id": "uuid",
        "order_number": "BSK-20261117-ABC123",
        "customer_id": "uuid | null",
        "is_guest": false,
        "quote_id": "uuid",
        "reservation_id": "uuid",
        "delivery_address": { ... },
        "subtotal_paise": 100000,
        "discount_total_paise": 10000,
        "delivery_fee_paise": 5000,
        "cgst_paise": 8100,
        "sgst_paise": 8100,
        "igst_paise": 0,
        "total_tax_paise": 16200,
        "total_payable_paise": 111200,
        "currency": "INR",
        "status": "PENDING_PAYMENT",
        "payment_status": "NOT_INITIATED",
        "payment_window_expires_at": "2026-11-17T15:15:00Z",
        "items": [ ... ],
        "created_at": "2026-11-17T15:00:00Z",
        "updated_at": "2026-11-17T15:00:00Z"
      }
    ],
    "total": 1
  }
  ```

### `GET /api/v1/orders/{order_id}`
- **Auth**: Required (`current_user` or validated guest session).
- **Description**: Retrieves full order details including line items, address snapshot, financial breakdown, and status history. Enforces strict tenant isolation; cross-tenant requests return `404 ORDER_NOT_FOUND`.
- **Response**: `200 OK` (`OrderResponse`).
