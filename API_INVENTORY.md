# BASKET — Comprehensive API Inventory & Endpoint Reference

> **Document Version:** 2.0.0  
> **Repository:** `Rahul2006MILLION/Online_Shopping`  
> **Base Path:** `/api/v1`  
> **Last Updated:** 2026-11-20  

---

## P3. Phase 3 Endpoints (verified 2026-11-20) — 53 new operations

> Total after Phase 3: **201 operations** (198 under `/api/v1` + `/health`, `/ready`, `/metrics`), generated from the running app.
> Schemas are in each module's `schemas.py` and the OpenAPI document (`/api/v1/openapi.json`, non-production). Frontend usage: `frontend/lib/api/phase3.ts` and **FRONTEND_INTEGRATION_GUIDE.md**. Paths are relative to `/api/v1`.

| Method | Endpoint | Auth / role | Request | Response | Errors |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/price-intelligence/listings/{listing_id}` | Public | `days` 7–90 | PriceIntelligence | 404 LISTING_NOT_FOUND, 422 |
| `GET` | `/sale-stream/live` | Public | `event_type, category_slug, before, since, limit≤50` | SaleStreamResponse | 422 |
| `GET` | `/i18n/languages` | Public | — | LanguagesResponse | — |
| `GET` | `/i18n/normalize` | Public | `q` 1–200 | NormalizedQueryResponse | 422 |
| `GET` | `/i18n/translations` | Public | `entity_type, lang, ids` (≤100) | TranslationsResponse | 422 INVALID_IDS/TOO_MANY_IDS/UNSUPPORTED_LANGUAGE |
| `GET` | `/i18n/preference` | Any signed-in user | — | `{language}` | 401 |
| `PUT` | `/i18n/preference` | Any signed-in user + CSRF | `{language}` | `{language}` | 401, 422 UNSUPPORTED_LANGUAGE |
| `PUT` | `/admin/i18n/translations` | Admin + CSRF | `{entity_type, entity_id, language, fields{name?,description?}}` | 204 | 403, 404 ENTITY_NOT_FOUND, 422 |
| `POST` | `/demand/signal` | Guest or customer + CSRF (cookie) | `{query_text?, listing_id?, category_id?, pincode?, signal_type}` | 201 `{pool, deduplicated}` | 403 (retailer/admin), 404, 409 LISTING_IN_STOCK, 422 |
| `POST` | `/demand/pools/{pool_id}/join` | Guest or customer | `{pincode?}` | 201 `{pool, deduplicated}` | 403, 404 DEMAND_POOL_NOT_FOUND |
| `GET` | `/demand/pools` | Public | `q, pincode, limit, offset` | DemandPoolList | 422 INVALID_PINCODE |
| `GET` | `/demand/my-requests` | Signed-in | — | DemandPoolList (with offers) | 401 |
| `GET` | `/retailer/demand-gaps` | Retailer | `pincode, category_id, limit, offset` | DemandPoolList | 403 |
| `POST` | `/retailer/demand-gaps/{pool_id}/fulfill` | Retailer (verified) + CSRF | `{listing_id, note?}` | DemandPool | 403 PINCODE_NOT_SERVICED/RETAILER_NOT_VERIFIED, 404, 409 ALREADY_RESPONDED |
| `GET` | `/admin/demand/pools` | Admin | `status, limit, offset` | DemandPoolList | 403 |
| `PATCH` | `/admin/demand/pools/{pool_id}` | Admin + CSRF | `{status?, visibility_threshold?}` | DemandPool | 404, 409 OPEN_POOL_EXISTS |
| `GET` | `/admin/demand/trends` | Admin | `days` 1–90 | DemandTrendsResponse | 403 |
| `GET` | `/community-buying/campaigns` | Public | `limit, offset` | CampaignList | — |
| `GET` | `/community-buying/campaigns/{id}` | Public | — | Campaign | 404 CAMPAIGN_NOT_FOUND |
| `POST` | `/community-buying/campaigns/{id}/join` | Customer + CSRF | `{quantity 1–10}` | Campaign | 401/403, 409 ALREADY_JOINED/CAMPAIGN_FULL/CAMPAIGN_CLOSED/INSUFFICIENT_STOCK, 422 QUANTITY_LIMIT |
| `POST` | `/community-buying/campaigns/{id}/leave` | Customer + CSRF | — | Campaign | 404 NOT_A_MEMBER, 409 |
| `GET` | `/community-buying/campaigns/{id}/share` | Customer | — | `{url, message, whatsapp_url, sms_url}` | 409 CAMPAIGN_CLOSED |
| `GET` | `/retailer/community-buying/campaigns` | Retailer | `status` | CampaignList | 403 |
| `POST` | `/retailer/community-buying/campaigns` | Retailer (verified, own listing) + CSRF | CampaignCreate | 201 Campaign | 403, 404, 409 LISTING_INACTIVE, 422 |
| `POST` | `/retailer/community-buying/campaigns/{id}/cancel` | Retailer (owner) + CSRF | — | Campaign | 404, 409 |
| `GET` | `/admin/community-buying/campaigns` | Admin | `status` | CampaignList | 403 |
| `POST` | `/admin/community-buying/campaigns` | Admin + CSRF | CampaignCreate | 201 Campaign | 404, 422 |
| `POST` | `/admin/community-buying/campaigns/{id}/cancel` | Admin + CSRF | — | Campaign | 404, 409 |
| `POST` | `/exchange/requests` | Customer + CSRF | `{title, delivery_pincode, budget_limit_paise?, items[1–20], bidding_hours}` | 201 ExchangeRequest | 422 |
| `GET` | `/exchange/requests` | Customer | `limit, offset` | ExchangeRequestList (bids) | 401/403 |
| `GET` | `/exchange/requests/{id}` | Customer (owner) | — | ExchangeRequest | 404 RFQ_NOT_FOUND |
| `POST` | `/exchange/requests/{id}/accept-bid` | Customer (owner) + CSRF | `{bid_id}` | AcceptBidResponse | 404 BID_NOT_FOUND, 409 RFQ_CLOSED/BID_NO_LONGER_AVAILABLE |
| `POST` | `/exchange/requests/{id}/cancel` | Customer (owner) + CSRF | — | ExchangeRequest | 404, 409 RFQ_CLOSED |
| `GET` | `/retailer/exchange/requests` | Retailer | `limit, offset` | ExchangeRequestList (my_bid only) | 403 |
| `POST` | `/retailer/exchange/requests/{id}/bids` | Retailer (verified) + CSRF | `{lines[{manifest_index, listing_id, unit_price_paise}], estimated_delivery_hours, notes?}` | 201 Bid | 403 PINCODE_NOT_SERVICED, 404, 409 RFQ_CLOSED/INSUFFICIENT_STOCK/BID_LOCKED, 422 BID_ABOVE_LIST_PRICE/BID_OVER_BUDGET/INVALID_BID_LINE |
| `DELETE` | `/retailer/exchange/requests/{id}/bids` | Retailer + CSRF | — | 204 | 404 |
| `GET` | `/admin/exchange/requests` | Admin | `status` | ExchangeRequestList (bids) | 403 |
| `POST` | `/negotiate/start` | Customer + CSRF | `{target_price_paise?, max_budget_paise?, language?}` | 201 NegotiationSession | 400 EMPTY_CART, 422 UNSUPPORTED_LANGUAGE, 429 NEGOTIATION_LIMIT |
| `POST` | `/negotiate/counter-offer` | Customer (owner) + CSRF | `{session_id, proposed_price_paise}` | NegotiationSession | 404, 409 CART_CHANGED/NEGOTIATION_CLOSED/MAX_ROUNDS_REACHED |
| `POST` | `/negotiate/accept` | Customer (owner) + CSRF | `{session_id}` | NegotiationSession (+quote_id) | 404, 409 |
| `GET` | `/negotiate/sessions/{id}` | Customer (owner) | — | NegotiationSession | 404 |
| `GET` | `/retailer/negotiation-rules` | Retailer | — | Rule[] | 403 |
| `PUT` | `/retailer/negotiation-rules` | Retailer + CSRF | RuleUpsert | Rule | 404, 422 FLOOR_ABOVE_PRICE/FLOOR_NEEDS_LISTING |
| `DELETE` | `/retailer/negotiation-rules/{rule_id}` | Retailer (owner) + CSRF | — | 204 | 404 RULE_NOT_FOUND |
| `POST` | `/auctions/start` | Customer + CSRF | `{pincode}` | 201 Auction | 400 EMPTY_CART, 409 AUCTION_IN_PROGRESS, 422 |
| `GET` | `/auctions/{id}/live` | Customer (owner) | `max_seconds`; `Accept: text/event-stream` for SSE | Auction / SSE | 404 |
| `POST` | `/auctions/{id}/accept` | Customer (owner) + CSRF | `{bid_id}` | `{auction, cart_id, message}` | 404, 409 AUCTION_STILL_LIVE/AUCTION_CLOSED/BID_NO_LONGER_AVAILABLE |
| `POST` | `/auctions/{id}/cancel` | Customer (owner) + CSRF | — | Auction | 409 |
| `GET` | `/retailer/auctions` | Retailer | — | AuctionList | 403 |
| `POST` | `/retailer/auctions/{id}/bid` | Retailer (verified) + CSRF | `{bid_price_paise, delivery_eta_minutes, warranty_note?}` | 201 AuctionBid | 403 PINCODE_NOT_SERVICED, 409 AUCTION_CLOSED, 422 BID_ABOVE_LIST_PRICE/BID_NOT_LOWER/CANNOT_FULFIL_BASKET |
| `GET` | `/admin/auctions` | Admin | `status` | AuctionList | 403 |
| `POST` | `/vision/parse-list` | Customer + CSRF | `{text}` or `{image_base64, content_type}` | ParseListResponse | 422 (validation), 502 OCR_PROVIDER_ERROR, 503 OCR_PROVIDER_UNAVAILABLE |
| `POST` | `/vision/build-cart` | Customer + CSRF | `{items[{listing_id, quantity}]}` | BuildCartResponse | 409 NOTHING_TO_ADD |

**Modified in Phase 3:** `GET /search` (adds `original_query, interpreted_query, detected_language, query_translated`; zero-result queries are logged as demand; `force_fallback` ignored in production; uses PostgreSQL when OpenSearch is unconfigured), `POST /quotes` and checkout (apply Phase 3 price awards), `POST /orders` (consumes awards), `PATCH /retailer/listings/{id}` and `POST /retailer/listings|products` (record price history, emit `price.changed`, Sale Stream price drops), `POST /retailer/offers` and `POST /admin/deals` (flash deals).

**Validation conventions:** PIN codes `^[1-9][0-9]{5}$`; quantities 1–10 (cart limit); all money integer paise > 0; ids are UUIDs; free text length-bounded per schema.

---

## 0. Verified Endpoint Inventory — 2026-11-20 (generated from the running app)

> Generated by walking the FastAPI router tree of `app.main:create_app()` (script kept at
> `backups/pre-audit-20261120/route_audit.py`, git-ignored). **148 operations**: 145 under
> `/api/v1` plus `/health`, `/ready`, `/metrics`. `/api/v1/catalogue/{categories,retailers,products,products/{id}}`
> are aliases of the un-prefixed catalogue routes (same handlers).
>
> **Auth column legend:** `AUTH` = `get_current_user` required · `ROLE` = role check (admin or retailer as the path implies) ·
> `RETAILER` = retailer profile resolved · `CSRF` = double-submit CSRF on cookie-authenticated unsafe methods ·
> `ADMIN_OR_INTERNAL` = admin JWT (+CSRF) or `X-Internal-Service-Key` · `INTERNAL` = internal service key only.
> Routes showing only `CSRF` or `-` resolve the caller **inside the handler** via `get_current_user_optional`
> (customer JWT/cookie **or** guest cart token) and enforce ownership in the service layer (orders, payments,
> reservations, quotes, cart, notifications). `/payments/webhook` is authenticated by Razorpay HMAC signature.

| Method | Path | Auth / protections |
| :--- | :--- | :--- |
| `GET` | `/health` | - |
| `GET` | `/ready` | - |
| `GET` | `/metrics` | - |
| `POST` | `/api/v1/auth/register` | - |
| `POST` | `/api/v1/auth/retailer/register` | - |
| `POST` | `/api/v1/auth/login` | - |
| `POST` | `/api/v1/auth/refresh` | - |
| `POST` | `/api/v1/auth/logout` | CSRF |
| `POST` | `/api/v1/auth/logout-all` | AUTH, CSRF |
| `GET` | `/api/v1/users/me` | AUTH |
| `GET` | `/api/v1/addresses` | AUTH |
| `POST` | `/api/v1/addresses` | AUTH, CSRF |
| `PATCH` | `/api/v1/addresses/{address_id}` | AUTH, CSRF |
| `DELETE` | `/api/v1/addresses/{address_id}` | AUTH, CSRF |
| `GET` | `/api/v1/categories` | - |
| `GET` | `/api/v1/retailers` | - |
| `GET` | `/api/v1/products` | - |
| `GET` | `/api/v1/products/{id}` | - |
| `GET` | `/api/v1/catalogue/categories` | - |
| `GET` | `/api/v1/catalogue/retailers` | - |
| `GET` | `/api/v1/catalogue/products` | - |
| `GET` | `/api/v1/catalogue/products/{id}` | - |
| `GET` | `/api/v1/search` | - |
| `GET` | `/api/v1/search/suggestions` | - |
| `GET` | `/api/v1/cart` | - |
| `POST` | `/api/v1/cart/items` | CSRF |
| `PATCH` | `/api/v1/cart/items/{item_id}` | CSRF |
| `DELETE` | `/api/v1/cart/items/{item_id}` | CSRF |
| `DELETE` | `/api/v1/cart` | CSRF |
| `GET` | `/api/v1/cart/items/{item_id}/substitutes` | - |
| `POST` | `/api/v1/cart/items/{item_id}/replace` | CSRF |
| `POST` | `/api/v1/cart/merge` | AUTH, CSRF |
| `POST` | `/api/v1/missions` | AUTH, CSRF |
| `POST` | `/api/v1/missions/preview` | - |
| `GET` | `/api/v1/missions` | AUTH |
| `GET` | `/api/v1/missions/{mission_id}` | AUTH |
| `PATCH` | `/api/v1/missions/{mission_id}` | AUTH, CSRF |
| `DELETE` | `/api/v1/missions/{mission_id}` | AUTH, CSRF |
| `POST` | `/api/v1/missions/{mission_id}/items` | AUTH, CSRF |
| `PATCH` | `/api/v1/missions/{mission_id}/items/{item_id}` | AUTH, CSRF |
| `DELETE` | `/api/v1/missions/{mission_id}/items/{item_id}` | AUTH, CSRF |
| `GET` | `/api/v1/missions/{mission_id}/items/{item_id}/alternatives` | AUTH |
| `POST` | `/api/v1/missions/{mission_id}/items/{item_id}/replace` | AUTH, CSRF |
| `POST` | `/api/v1/missions/{mission_id}/add-to-cart` | AUTH, CSRF |
| `GET` | `/api/v1/substitutes/listings/{listing_id}` | - |
| `GET` | `/api/v1/intent/overview` | AUTH |
| `GET` | `/api/v1/intent/profile` | AUTH |
| `PUT` | `/api/v1/intent/profile` | AUTH, CSRF |
| `PATCH` | `/api/v1/intent/consent` | AUTH, CSRF |
| `GET` | `/api/v1/intent/recurring` | AUTH |
| `POST` | `/api/v1/intent/recurring` | AUTH, CSRF |
| `PUT` | `/api/v1/intent/recurring/{intention_id}` | AUTH, CSRF |
| `PATCH` | `/api/v1/intent/recurring/{intention_id}/status` | AUTH, CSRF |
| `DELETE` | `/api/v1/intent/recurring/{intention_id}` | AUTH, CSRF |
| `GET` | `/api/v1/intent/memories` | AUTH |
| `POST` | `/api/v1/intent/memories` | AUTH, CSRF |
| `DELETE` | `/api/v1/intent/memories/{memory_id}` | AUTH, CSRF |
| `DELETE` | `/api/v1/intent/clear-all` | AUTH, CSRF |
| `GET` | `/api/v1/intent/suggestions` | AUTH |
| `GET` | `/api/v1/passport/products/{id}` | - |
| `GET` | `/api/v1/products/{id}/passport` | - |
| `GET` | `/api/v1/passport/listings/{listing_id}` | - |
| `GET` | `/api/v1/retailer/passport/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `PUT` | `/api/v1/retailer/passport/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/passport/listings/{listing_id}/claims` | ROLE, RETAILER, AUTH, CSRF |
| `PUT` | `/api/v1/retailer/passport/claims/{claim_id}` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/passport/claims` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/passport/claims/{claim_id}/history` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/admin/passport/queue` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/passport/claims/{claim_id}/verify` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/passport/claims/{claim_id}/reject` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/passport/claims/{claim_id}/history` | ROLE, AUTH, CSRF |
| `PUT` | `/api/v1/admin/passport/products/{product_id}` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/checkout/quote` | CSRF |
| `POST` | `/api/v1/quotes` | CSRF |
| `GET` | `/api/v1/quotes/{quote_id}` | CSRF |
| `POST` | `/api/v1/quotes/{quote_id}/validate` | CSRF |
| `POST` | `/api/v1/quotes/{quote_id}/refresh` | CSRF |
| `GET` | `/api/v1/quotes` | AUTH, CSRF |
| `POST` | `/api/v1/reservations` | CSRF |
| `GET` | `/api/v1/reservations/{reservation_id}` | CSRF |
| `POST` | `/api/v1/reservations/{reservation_id}/release` | CSRF |
| `POST` | `/api/v1/internal/reservations/cleanup-expired` | INTERNAL |
| `POST` | `/api/v1/orders` | CSRF |
| `GET` | `/api/v1/orders` | CSRF |
| `POST` | `/api/v1/orders/guest-lookup` | CSRF |
| `GET` | `/api/v1/orders/{order_id}` | CSRF |
| `POST` | `/api/v1/orders/{order_id}/cancel` | CSRF |
| `GET` | `/api/v1/orders/{order_id}/tracking` | CSRF |
| `POST` | `/api/v1/orders/{order_id}/shipments` | ADMIN_OR_INTERNAL, CSRF |
| `PATCH` | `/api/v1/orders/{order_id}/shipments/{shipment_id}` | ADMIN_OR_INTERNAL, CSRF |
| `POST` | `/api/v1/orders/{order_id}/returns` | CSRF |
| `GET` | `/api/v1/orders/{order_id}/returns` | CSRF |
| `PATCH` | `/api/v1/returns/{return_id}/status` | ADMIN_OR_INTERNAL, CSRF |
| `GET` | `/api/v1/notifications` | CSRF |
| `GET` | `/api/v1/notifications/unread-count` | CSRF |
| `POST` | `/api/v1/notifications/{notification_id}/read` | CSRF |
| `POST` | `/api/v1/orders/{order_id}/payments` | CSRF |
| `POST` | `/api/v1/orders/{order_id}/payments/verify` | CSRF |
| `POST` | `/api/v1/orders/{order_id}/refunds` | ADMIN_OR_INTERNAL, CSRF |
| `POST` | `/api/v1/payments/webhook` | CSRF |
| `POST` | `/api/v1/internal/payments/reconcile-pending` | INTERNAL |
| `POST` | `/api/v1/internal/payments/{payment_id}/resolve-ambiguity` | INTERNAL |
| `POST` | `/api/v1/internal/payments/sla-escalation` | INTERNAL |
| `GET` | `/api/v1/retailer/profile` | ROLE, RETAILER, AUTH, CSRF |
| `PUT` | `/api/v1/retailer/profile` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/overview` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/catalogue/products` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/listings` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/listings` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `PATCH` | `/api/v1/retailer/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `PUT` | `/api/v1/retailer/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `DELETE` | `/api/v1/retailer/listings/{listing_id}` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/inventory` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/listings/{listing_id}/inventory` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/inventory/bulk-adjust` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/products` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/orders` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/orders/{order_id}` | ROLE, RETAILER, AUTH, CSRF |
| `PATCH` | `/api/v1/retailer/orders/{order_id}/status` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/offers` | ROLE, RETAILER, AUTH, CSRF |
| `POST` | `/api/v1/retailer/offers` | ROLE, RETAILER, AUTH, CSRF |
| `PUT` | `/api/v1/retailer/offers/{offer_id}` | ROLE, RETAILER, AUTH, CSRF |
| `DELETE` | `/api/v1/retailer/offers/{offer_id}` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/retailer/analytics` | ROLE, RETAILER, AUTH, CSRF |
| `GET` | `/api/v1/admin/overview` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/retailers` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/retailers/{retailer_id}` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/retailers/{retailer_id}/analytics` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/retailers/{retailer_id}/verify` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/retailers/{retailer_id}/documents/{document_id}/verify` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/catalogue/products` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/catalogue/products` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/catalogue/products/{product_id}` | ROLE, AUTH, CSRF |
| `PUT` | `/api/v1/admin/catalogue/products/{product_id}` | ROLE, AUTH, CSRF |
| `DELETE` | `/api/v1/admin/catalogue/products/{product_id}` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/catalogue/products/{product_id}/variants` | ROLE, AUTH, CSRF |
| `PUT` | `/api/v1/admin/catalogue/variants/{variant_id}` | ROLE, AUTH, CSRF |
| `DELETE` | `/api/v1/admin/catalogue/variants/{variant_id}` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/catalogue/categories` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/catalogue/categories` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/deals` | ROLE, AUTH, CSRF |
| `POST` | `/api/v1/admin/deals` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/admin/deals/{deal_id}` | ROLE, AUTH, CSRF |
| `PUT` | `/api/v1/admin/deals/{deal_id}` | ROLE, AUTH, CSRF |
| `DELETE` | `/api/v1/admin/deals/{deal_id}` | ROLE, AUTH, CSRF |
| `GET` | `/api/v1/info` | - |

### 0.1 Contract changes made in this audit

| Endpoint | Before | After |
| :--- | :--- | :--- |
| `POST /api/v1/orders/{order_id}/shipments` | unauthenticated | `ADMIN_OR_INTERNAL` |
| `PATCH /api/v1/orders/{order_id}/shipments/{shipment_id}` | unauthenticated, any transition | `ADMIN_OR_INTERNAL`, state machine (`409 INVALID_SHIPMENT_TRANSITION`) |
| `PATCH /api/v1/returns/{return_id}/status` | unauthenticated, any transition | `ADMIN_OR_INTERNAL`, state machine (`409 INVALID_RETURN_TRANSITION`) |
| `POST /api/v1/orders/{order_id}/refunds` | customer, guest or internal | `ADMIN_OR_INTERNAL` (customers `403`) |
| `PATCH /api/v1/retailer/orders/{order_id}/status` | allowed on unpaid orders | `409` unless order is paid and live; cancellation restocks + refunds |
| Retailer / admin / passport / orders / payments / reservations / quotes routers | CSRF on some customer routes only | router-level CSRF (safe methods exempt) |
| `GET /ready` | `kafka.status = connected` if configured | real publisher state + `outbox_pending` / `outbox_failed` |

---


## 1. System & Observability Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | Health | None | Public | Liveness probe returning process state | `200 OK` |
| `GET` | `/ready` | Health | None | Public | Readiness probe checking DB, Kafka, OpenSearch | `200 OK`, `503 Unavailable` |
| `GET` | `/metrics` | Observability | None | Internal | Prometheus metrics in text format 0.0.4 | `200 OK` |
| `GET` | `/api/v1/info` | System | None | Public | Service metadata, environment, and API version | `200 OK` |

---

## 2. Identity, Authentication & Profile Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Authentication | None | Public | Register customer account | `RegisterRequest` | `201 Created` |
| `POST` | `/api/v1/auth/retailer/register` | Authentication | None | Public | Register retailer account | `RetailerRegisterRequest` | `201 Created` |
| `POST` | `/api/v1/auth/login` | Authentication | None | Public | Authenticate user, issue JWT cookies | `LoginRequest` | `200 OK` |
| `POST` | `/api/v1/auth/refresh` | Authentication | Refresh Cookie | Authenticated | Rotate access token via refresh token | None | `200 OK` |
| `POST` | `/api/v1/auth/logout` | Authentication | Access Token | Authenticated | Revoke current session & clear cookies | None | `200 OK` |
| `POST` | `/api/v1/auth/logout-all` | Authentication | Access Token | Authenticated | Revoke all active sessions for user | None | `200 OK` |
| `GET` | `/api/v1/users/me` | Users | Access Token | Authenticated | Fetch authenticated user profile & role | None | `200 OK` |
| `GET` | `/api/v1/addresses` | Addresses | Access Token | Customer | List saved delivery addresses | None | `200 OK` |
| `POST` | `/api/v1/addresses` | Addresses | Access Token | Customer | Add new delivery address | `AddressCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/addresses/{address_id}` | Addresses | Access Token | Customer | Update existing address details | `AddressUpdateRequest` | `200 OK` |
| `DELETE`| `/api/v1/addresses/{address_id}` | Addresses | Access Token | Customer | Delete saved address | None | `200 OK` |

---

## 3. Public Catalogue & Taxonomy Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Query Parameters | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/catalogue/categories` | Catalogue | None | Public | List hierarchical category tree | `parent_id`, `is_active` | `200 OK` |
| `GET` | `/api/v1/categories` | Catalogue | None | Public | Alias for category listing | `parent_id` | `200 OK` |
| `GET` | `/api/v1/catalogue/products` | Catalogue | None | Public | Browse products with pagination | `category_id`, `brand`, `page` | `200 OK` |
| `GET` | `/api/v1/products` | Catalogue | None | Public | Alias for product listing | `category_id`, `brand`, `page` | `200 OK` |
| `GET` | `/api/v1/catalogue/products/{id}` | Catalogue | None | Public | Get canonical product details & variants | None | `200 OK` |
| `GET` | `/api/v1/products/{id}` | Catalogue | None | Public | Alias for product detail | None | `200 OK` |
| `GET` | `/api/v1/catalogue/retailers` | Catalogue | None | Public | List verified public retailers | `city`, `is_active` | `200 OK` |
| `GET` | `/api/v1/retailers` | Catalogue | None | Public | Alias for retailer listing | `city` | `200 OK` |

---

## 4. Search & Discovery Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Query Parameters | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/search` | Search | None | Public | Faceted search with OpenSearch & DB fallback | `q`, `category`, `price_min`, `price_max` | `200 OK` |
| `GET` | `/api/v1/search/suggestions` | Search | None | Public | Autocomplete query suggestions | `q`, `limit` | `200 OK` |

---

## 5. Universal Shopping Cart Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/cart` | Cart | Session / Token | Guest / Customer | Retrieve active cart with computed prices | None | `200 OK` |
| `DELETE`| `/api/v1/cart` | Cart | Session / Token | Guest / Customer | Clear all items from active cart | None | `200 OK` |
| `POST` | `/api/v1/cart/items` | Cart | Session / Token | Guest / Customer | Add listing item to cart | `CartItemCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/cart/items/{item_id}`| Cart | Session / Token | Guest / Customer | Update quantity of cart item | `CartItemUpdateRequest` | `200 OK` |
| `DELETE`| `/api/v1/cart/items/{item_id}`| Cart | Session / Token | Guest / Customer | Remove specific item from cart | None | `200 OK` |
| `POST` | `/api/v1/cart/merge` | Cart | Access Token | Customer | Merge guest session cart into user cart | `CartMergeRequest` | `200 OK` |

---

## 6. Pricing, Deals & Cryptographic Quotes

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/checkout/quote` | Pricing | Session / Token | Guest / Customer | Generate HMAC-signed checkout quote | `QuoteCreateRequest` | `201 Created` |
| `POST` | `/api/v1/quotes` | Pricing | Session / Token | Guest / Customer | Alias for quote creation | `QuoteCreateRequest` | `201 Created` |
| `GET` | `/api/v1/quotes` | Pricing | Access Token | Customer | List historical quotes for user | None | `200 OK` |
| `GET` | `/api/v1/quotes/{quote_id}` | Pricing | Access Token | Customer | Fetch specific quote details | None | `200 OK` |
| `POST` | `/api/v1/quotes/{quote_id}/validate` | Pricing | Session / Token | Guest / Customer | Validate HMAC signature & expiration | None | `200 OK` |
| `POST` | `/api/v1/quotes/{quote_id}/refresh` | Pricing | Session / Token | Guest / Customer | Refresh expired quote prices | None | `200 OK` |

---

## 7. Inventory Reservations & Concurrency

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reservations` | Inventory | Access Token | Customer | Lock stock for 10 min using row locks | `ReservationCreateRequest` | `201 Created` |
| `GET` | `/api/v1/reservations/{reservation_id}` | Inventory | Access Token | Customer | Check reservation status & TTL | None | `200 OK` |
| `POST` | `/api/v1/reservations/{reservation_id}/release`| Inventory | Access Token | Customer | Manually release stock reservation | None | `200 OK` |

---

## 8. Orders, Shipments & Returns Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/orders` | Orders | Access Token | Customer | List customer orders | None | `200 OK` |
| `POST` | `/api/v1/orders` | Orders | Access Token | Customer | Place order with quote & reservation | `OrderCreateRequest` | `201 Created` |
| `GET` | `/api/v1/orders/{order_id}` | Orders | Access Token | Customer | Fetch order details & item snapshots | None | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Orders | Access Token | Customer | Cancel unfulfilled order | `OrderCancelRequest` | `200 OK` |
| `GET` | `/api/v1/orders/{order_id}/tracking` | Orders | Access Token | Customer | Track order fulfillment timeline | None | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/shipments` | Orders | Access Token | Admin / Retailer | Create shipment & tracking number | `ShipmentCreateRequest` | `201 Created` |
| `PATCH`| `/api/v1/orders/{order_id}/shipments/{shipment_id}`| Orders | Access Token | Admin / Retailer | Update courier dispatch status | `ShipmentUpdateRequest` | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/returns` | Orders | Access Token | Customer | Request post-delivery item return | `ReturnCreateRequest` | `201 Created` |
| `GET` | `/api/v1/orders/{order_id}/returns` | Orders | Access Token | Customer | List return requests for order | None | `200 OK` |
| `PATCH`| `/api/v1/returns/{return_id}/status` | Orders | Access Token | Retailer / Admin | Approve or reject return request | `ReturnStatusUpdateRequest`| `200 OK` |

---

## 9. Payments & Razorpay Integration Endpoints

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/orders/{order_id}/payments` | Payments | Access Token | Customer | Create Razorpay order | `PaymentInitiateRequest` | `201 Created` |
| `POST` | `/api/v1/orders/{order_id}/payments/verify` | Payments | Access Token | Customer | Verify Razorpay payment signature | `PaymentVerifyRequest` | `200 OK` |
| `POST` | `/api/v1/payments/webhook` | Payments | Webhook HMAC | Razorpay Service| Ingest Razorpay asynchronous webhooks | Webhook Payload | `200 OK` |
| `POST` | `/api/v1/orders/{order_id}/refunds` | Payments | Access Token | Admin | Issue partial or full order refund | `RefundCreateRequest` | `201 Created` |

---

## 10. Customer Intelligence: Basket Mission (Phase 2A)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/missions/plan` | Basket Mission | None / Token | Public / Customer | Generate budget-optimized knapsack basket | `MissionPlanRequest` | `200 OK` |
| `GET` | `/api/v1/missions/thematic` | Basket Mission | None / Token | Public / Customer | Get curated thematic shopping missions | `theme_id` | `200 OK` |
| `POST` | `/api/v1/missions/sync-to-cart`| Basket Mission | Session / Token | Guest / Customer | Sync mission items into active cart | `MissionSyncRequest` | `200 OK` |

---

## 11. Customer Intelligence: Substitute Intelligence (Phase 2B)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/substitutes/listings/{listing_id}` | Substitutes | None / Token | Public / Customer | Get 5-tier ranked product alternatives | `tier`, `max_price` | `200 OK` |
| `GET` | `/api/v1/cart/items/{item_id}/substitutes` | Cart | Session / Token | Guest / Customer | Get alternatives for item in cart | None | `200 OK` |
| `POST` | `/api/v1/cart/items/{item_id}/replace` | Cart | Session / Token | Guest / Customer | Atomically replace cart item with alternative | `CartItemReplaceRequest` | `200 OK` |

---

## 12. Customer Intelligence: Basket Intent Memory (Phase 2C)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/intent/overview` | Intent Memory | Access Token | Customer | Get customer intent profile & recurring items| None | `200 OK` |
| `GET` | `/api/v1/intent/profile` | Intent Memory | Access Token | Customer | Get preference profile | None | `200 OK` |
| `PUT` | `/api/v1/intent/profile` | Intent Memory | Access Token | Customer | Upsert dietary & brand preferences | `IntentProfileUpsertRequest` | `200 OK` |
| `PATCH`| `/api/v1/intent/consent` | Intent Memory | Access Token | Customer | Explicitly toggle personalization consent | `ConsentUpdateRequest` | `200 OK` |
| `GET` | `/api/v1/intent/memories` | Intent Memory | Access Token | Customer | List recurring shopping intentions | None | `200 OK` |
| `POST` | `/api/v1/intent/memories` | Intent Memory | Access Token | Customer | Create recurring intention card | `RecurringIntentionCreate` | `201 Created` |
| `DELETE`| `/api/v1/intent/memories/{id}`| Intent Memory | Access Token | Customer | Delete specific recurring intention | None | `200 OK` |
| `DELETE`| `/api/v1/intent/clear-all` | Intent Memory | Access Token | Customer | Complete erasure of all intent memory data | None | `200 OK` |

---

## 13. Customer Intelligence: Product Passport (Phase 2D)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Request / Body | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/passport/products/{id}` | Product Passport | None | Public | Get canonical product specifications | None | `200 OK` |
| `GET` | `/api/v1/products/{id}/passport` | Product Passport | None | Public | Alias for product passport | None | `200 OK` |
| `GET` | `/api/v1/passport/listings/{listing_id}`| Product Passport | None | Public | Get retailer listing passport & verified claims| None | `200 OK` |
| `GET` | `/api/v1/retailer/passport/listings/{id}`| Retailer Passport | Access Token | Retailer | Get store listing passport details | None | `200 OK` |
| `PUT` | `/api/v1/retailer/passport/listings/{id}`| Retailer Passport | Access Token | Retailer | Upsert listing batch, warranty, specs | `ListingPassportUpsert` | `200 OK` |
| `POST` | `/api/v1/retailer/passport/listings/{id}/claims`| Retailer Passport | Access Token | Retailer | Submit listing claim for moderation | `ClaimSubmitRequest` | `201 Created` |
| `GET` | `/api/v1/retailer/passport/claims` | Retailer Passport | Access Token | Retailer | List submitted claims and verification states | None | `200 OK` |
| `PUT` | `/api/v1/retailer/passport/claims/{id}` | Retailer Passport | Access Token | Retailer | Edit claim (auto-resets to PENDING) | `ClaimUpdateRequest` | `200 OK` |
| `GET` | `/api/v1/retailer/passport/claims/{id}/history`| Retailer Passport | Access Token | Retailer | View immutable revision & review history | None | `200 OK` |
| `GET` | `/api/v1/admin/passport/queue` | Admin Passport | Access Token | Admin | Review pending claims moderation queue | `status`, `page` | `200 OK` |
| `POST` | `/api/v1/admin/passport/claims/{id}/verify` | Admin Passport | Access Token | Admin | Approve & verify claim with auditor notes | None | `200 OK` |
| `POST` | `/api/v1/admin/passport/claims/{id}/reject` | Admin Passport | Access Token | Admin | Reject claim with mandatory reason | `ClaimRejectRequest` | `200 OK` |
| `GET` | `/api/v1/admin/passport/claims/{id}/history`| Admin Passport | Access Token | Admin | Inspect complete review decision audit trail | None | `200 OK` |
| `PUT` | `/api/v1/admin/passport/products/{id}` | Admin Passport | Access Token | Admin | Create or update canonical product passport | `CanonicalPassportUpsert`| `200 OK` |

---

## 14. Retailer Management Portal (`/api/v1/retailer/*`)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/retailer/overview` | Retailer Portal | Access Token | Retailer | Store KPI metrics, sales, and low-stock alerts | `200 OK` |
| `GET` | `/api/v1/retailer/profile` | Retailer Portal | Access Token | Retailer | Fetch store profile, GSTIN, and business details | `200 OK` |
| `PUT` | `/api/v1/retailer/profile` | Retailer Portal | Access Token | Retailer | Update store profile details | `200 OK` |
| `GET` | `/api/v1/retailer/catalogue/products` | Retailer Portal | Access Token | Retailer | Browse global catalogue to map listings | `200 OK` |
| `POST` | `/api/v1/retailer/products` | Retailer Portal | Access Token | Retailer | Request custom product addition to catalogue | `201 Created` |
| `GET` | `/api/v1/retailer/listings` | Retailer Portal | Access Token | Retailer | List store product listings and active status | `200 OK` |
| `POST` | `/api/v1/retailer/listings` | Retailer Portal | Access Token | Retailer | Create new listing from product variant | `201 Created` |
| `GET` | `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Get listing details and pricing | `200 OK` |
| `PUT` | `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Update listing price or active state | `200 OK` |
| `DELETE`| `/api/v1/retailer/listings/{id}` | Retailer Portal | Access Token | Retailer | Soft-delete / deactivate listing | `200 OK` |
| `GET` | `/api/v1/retailer/inventory` | Retailer Portal | Access Token | Retailer | Inventory overview across all listings | `200 OK` |
| `POST` | `/api/v1/retailer/listings/{id}/inventory` | Retailer Portal | Access Token | Retailer | Adjust stock quantity for single listing | `200 OK` |
| `POST` | `/api/v1/retailer/inventory/bulk-adjust` | Retailer Portal | Access Token | Retailer | Bulk update inventory levels via batch payload | `200 OK` |
| `GET` | `/api/v1/retailer/orders` | Retailer Portal | Access Token | Retailer | List orders containing store listings | `200 OK` |
| `GET` | `/api/v1/retailer/orders/{id}` | Retailer Portal | Access Token | Retailer | View itemized fulfillment details | `200 OK` |
| `PATCH`| `/api/v1/retailer/orders/{id}/status` | Retailer Portal | Access Token | Retailer | Update item dispatch / fulfillment state | `200 OK` |
| `GET` | `/api/v1/retailer/offers` | Retailer Portal | Access Token | Retailer | List store promotional discounts | `200 OK` |
| `POST` | `/api/v1/retailer/offers` | Retailer Portal | Access Token | Retailer | Create store-specific discount campaign | `201 Created` |
| `PUT` | `/api/v1/retailer/offers/{id}` | Retailer Portal | Access Token | Retailer | Modify offer parameters | `200 OK` |
| `DELETE`| `/api/v1/retailer/offers/{id}` | Retailer Portal | Access Token | Retailer | Terminate active offer | `200 OK` |
| `GET` | `/api/v1/retailer/analytics` | Retailer Portal | Access Token | Retailer | Revenue, order volume, and return analytics | `200 OK` |

---

## 15. Administrator Management Portal (`/api/v1/admin/*`)

| Method | Endpoint | Module / Tag | Auth | Role | Description | Response Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/admin/overview` | Admin Portal | Access Token | Admin | Platform GMV, orders, user count, active stores | `200 OK` |
| `GET` | `/api/v1/admin/retailers` | Admin Portal | Access Token | Admin | List all registered retailers with verification state | `200 OK` |
| `GET` | `/api/v1/admin/retailers/{id}` | Admin Portal | Access Token | Admin | Retailer compliance & business profile details | `200 OK` |
| `POST` | `/api/v1/admin/retailers/{id}/verify` | Admin Portal | Access Token | Admin | Verify and activate retailer for public sales | `200 OK` |
| `POST` | `/api/v1/admin/retailers/{id}/documents/{doc_id}/verify` | Admin Portal | Access Token | Admin | Verify uploaded GSTIN / PAN / FSSAI document | `200 OK` |
| `GET` | `/api/v1/admin/retailers/{id}/analytics` | Admin Portal | Access Token | Admin | Performance audit for specific store | `200 OK` |
| `GET` | `/api/v1/admin/catalogue/categories` | Admin Portal | Access Token | Admin | Manage global category tree | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/categories` | Admin Portal | Access Token | Admin | Add new category to global hierarchy | `201 Created` |
| `GET` | `/api/v1/admin/catalogue/products` | Admin Portal | Access Token | Admin | List canonical catalogue products | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/products` | Admin Portal | Access Token | Admin | Create new canonical product | `201 Created` |
| `GET` | `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Canonical product detail with variants | `200 OK` |
| `PUT` | `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Update canonical product specs & brand | `200 OK` |
| `DELETE`| `/api/v1/admin/catalogue/products/{id}` | Admin Portal | Access Token | Admin | Soft-delete / deactivate product | `200 OK` |
| `POST` | `/api/v1/admin/catalogue/products/{id}/variants` | Admin Portal | Access Token | Admin | Add SKU variant to product | `201 Created` |
| `PUT` | `/api/v1/admin/catalogue/variants/{id}` | Admin Portal | Access Token | Admin | Update variant attributes & MRP | `200 OK` |
| `DELETE`| `/api/v1/admin/catalogue/variants/{id}` | Admin Portal | Access Token | Admin | Deactivate variant SKU | `200 OK` |
| `GET` | `/api/v1/admin/deals` | Admin Portal | Access Token | Admin | List platform-wide deals | `200 OK` |
| `POST` | `/api/v1/admin/deals` | Admin Portal | Access Token | Admin | Create platform-sponsored deal | `201 Created` |
| `GET` | `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Fetch deal parameters | `200 OK` |
| `PUT` | `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Modify deal dates & percentages | `200 OK` |
| `DELETE`| `/api/v1/admin/deals/{id}` | Admin Portal | Access Token | Admin | Deactivate deal | `200 OK` |
