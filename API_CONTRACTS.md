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
