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
