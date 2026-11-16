# BASKET — Project Charter

## 1. Product objective

Build a credible, multi-category online shopping platform for a retail chain expanding across India. The platform must support product discovery, search, cart management, order placement, and a reliable event-driven order flow.

BASKET should distinguish itself through useful, explainable shopping intelligence—not a large collection of superficial AI buttons.

## 2. Core customer journey (mandatory)

1. Browse a product catalogue.
2. Search and filter products.
3. View product details, variants, seller, price, and availability.
4. Add and remove items from the cart.
5. Validate current price and stock on the server.
6. Place an order using a safe inventory reservation flow.
7. Complete a sandbox payment or clearly labelled demo payment flow.
8. View order confirmation and order status.

This flow must work end-to-end before optional features are expanded.

## 3. Mandatory infrastructure responsibilities

| Technology | Required responsibility |
|---|---|
| Aiven PostgreSQL | System of record for users, catalogue, inventory, prices, carts, orders, reservations, payments |
| Aiven Apache Kafka | Real order-domain events and asynchronous consumers |
| Aiven OpenSearch | Product search and filtering |

These services must do actual work in the demo. Merely displaying connection status is insufficient.

## 4. Product boundaries

- PostgreSQL is authoritative for price, stock, reservation, order, and payment state.
- OpenSearch is a derived search index. It must never authorize checkout or determine final stock.
- Kafka transports domain events. It is not the system of record.
- AI may recommend or explain. It cannot independently authorize price changes, inventory changes, payments, or order transitions.
- Every external integration must have an adapter boundary and an honest fallback.

## 5. Feature portfolio and priority

### P0 — must be complete
- Product catalogue and product details
- Search backed by OpenSearch
- Cart
- Checkout and order creation
- Transaction-safe inventory reservation
- PostgreSQL persistence
- Order event published through Kafka
- At least one real Kafka consumer
- Basic admin/retailer seed or catalogue workflow
- Error handling, logs, tests, and demo readiness

### P1 — add only after P0 passes
- Sale Storm: concurrency and oversell protection demonstration
- Quinn: bounded negotiation/quote workflow with server-enforced limits
- Apni Bhasha: multilingual search or shopping interface
- Basket Suggests: like-for-like comparison for the same exact variant and fulfilment context
- Demand Gap Radar: identify unmet demand from observed platform signals

### P2 — choose one or two only if time and quality allow
- Basket Mission: outcome-based, editable cross-category shopping plan
- Demand Exchange: retailer offers against structured Demand Boxes
- Product Proof: evidence-backed product claims and provenance
- BASKET LIVE: voice-first interface, behind a provider adapter
- Basket Intent Memory, Substitute Intelligence, Deals for You, Buy It Again

Do not implement every feature merely to increase feature count.

## 6. Product sourcing and trust

Use curated seed data, retailer-provided files, authorized feeds, or APIs with documented reuse rights. Store provenance and ingestion timestamps.

Separate:
- **BASKET Marketplace:** retailer is onboarded and BASKET supports the in-platform transaction.
- **BASKET Discovery:** external listing that redirects to the original retailer. Do not imply BASKET fulfils the order.

Do not bypass login, CAPTCHA, paywalls, anti-bot controls, private endpoints, or account/checkout pages. Public visibility alone does not establish permission to reuse data.

Only reviewed and approved products should become customer-visible. Approval does not guarantee current price or stock; freshness must be represented.

## 7. Success criteria

A judge should be able to:
- Search and find products through OpenSearch.
- Add a product to a cart and place an order.
- See inventory protected against concurrent checkout attempts.
- Observe an order event in Kafka and a consumer reaction.
- Verify the resulting order and inventory state in PostgreSQL.
- Understand which features are production-like, sandboxed, mocked, or demonstrative.

## 8. Explicit non-goals for the hackathon

- Kubernetes or elaborate microservice infrastructure
- Multiple competing databases or unnecessary caches
- Unbounded autonomous agents
- LLM-generated SQL or direct database mutation
- Fake integrations presented as live integrations
- Large numbers of incomplete feature screens
