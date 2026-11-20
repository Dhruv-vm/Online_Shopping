# BASKET — Frontend Integration Guide (Phase 1–3, redesign-ready)

> Audience: the frontend redesign. Source of truth for contracts is the running API
> (`/api/v1/openapi.json` in non-production) and `frontend/lib/api/*.ts`. Last verified 2026-11-20
> on branch `feature/phase-3-advanced-marketplace`.

## 1. Global conventions

| Topic | Contract |
| :--- | :--- |
| Base URL | `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`); all business routes under `/api/v1`. |
| Auth | HttpOnly `access_token` cookie (15 min) + `refresh_token` (7 d, path `/api/v1/auth`). `Authorization: Bearer` also accepted. The shared client refreshes on 401 automatically. |
| CSRF | Cookie-authenticated **POST/PUT/PATCH/DELETE** must send `X-CSRF-Token` equal to the `XSRF-TOKEN` cookie. `lib/api/client.ts` does this for you. GET/HEAD are exempt. |
| Guests | Guest identity = `basket_guest_cart` cookie (or `X-Guest-Cart-Token`). Guests may browse, cart, check out, and log demand signals. |
| Errors | Always `{"error": {"code", "message", "details"}}` → `ApiClientError {code, status, message, details}`. Switch UI on `code`, not on text. 422 = validation (field `details`), 401 = sign in, 403 = wrong role / CSRF, 404 = not found **or not yours**, 409 = state conflict, 429 = rate/quota, 503 = dependency unavailable. |
| Money | Integer **paise** everywhere (`formatPrice(paise)` in `lib/utils.ts`). Never compute final prices client-side; render what the server returns. |
| Time | ISO-8601 UTC. Countdown endpoints also return `seconds_remaining` (server-computed). |
| Pagination | `limit`/`offset` with `total`; Sale Stream uses cursors (`before`, `since`). |
| Loading/error UI | Every Phase 3 page uses `components/phase3/kit.tsx` (`useLoad`, `Status`, `Notice`, `Countdown`) — reuse or replace these in the redesign. |

### 1.1 Roles (backend-enforced)

| Capability | Customer | Retailer | Admin | Guest |
| :--- | :---: | :---: | :---: | :---: |
| Browse, search, Sale Stream, price history, group-buy list | ✅ | ✅ | ✅ | ✅ |
| Demand signal / join pool | ✅ | ❌ 403 | ❌ 403 | ✅ (total demand only) |
| Join group buy, RFQ, negotiate, auction, list-to-basket | ✅ | ❌ 403 | ❌ 403 | ❌ 401 |
| Create group buy, bid on RFQ/auction, demand fulfil, negotiation rules | ❌ | ✅ (own listings, verified store) | group buy only | ❌ |
| Demand thresholds, monitoring, translations, cancel any group buy | ❌ | ❌ | ✅ | ❌ |
| Shipments, return status, refunds (Phase 1 back-office) | ❌ | ❌ | ✅ (or service key) | ❌ |

### 1.2 Product & image data
* Search items (`GET /search`): `product_id, name, slug, brand, category_*, primary_image_url, min/max_price_paise, is_in_stock, total_available_quantity, retailers[] {retailer_id, retailer_name, listing_id, selling_price_paise, original_price_paise, is_in_stock, available_quantity}, variants[]`. Phase 3H adds `original_query, interpreted_query, detected_language, query_translated` (show “Showing results for *milk*”).
* Images are absolute `http(s)` URLs (validated server-side). There is **no upload/object storage** yet (DISC-01): use `<img>`/`next/image` with remote patterns; expect missing images (`null`).
* Prices shown at PDP are list prices; the authoritative charge is the **quote** (`POST /quotes`), which applies offers and Phase 3 price awards.

### 1.3 Checkout & Razorpay (unchanged)
Cart → `POST /quotes` → `POST /reservations {quote_id}` → `POST /orders {quote_id, reservation_id, delivery_address_id}` → `POST /orders/{id}/payments` → Razorpay Checkout → `POST /orders/{id}/payments/verify` (server verifies signature and captures). **Never** treat the Razorpay `handler` callback as success; only the verify response is authoritative.

### 1.4 Phase 3 special prices (“price awards”)
Negotiation, group buys, RFQ bids and auctions issue **single-use, time-limited price awards** to the customer. They are applied automatically when the customer's next quote is generated and consumed when an order is placed. UI implications: after accepting a deal, send the user to the basket/checkout; the quote line shows `unit_discounted_price_paise` at the deal price. Awards expire (negotiation 15 min, auction 30 min, group buy/RFQ 48 h).

## 2. Feature contracts

Client functions are in `frontend/lib/api/phase3.ts` (typed). Paths below are relative to `/api/v1`.

### 3A Demand Gap
| Endpoint | Role | Notes |
| :--- | :--- | :--- |
| `POST /demand/signal` `{query_text?, listing_id?, category_id?, pincode?, signal_type: "WISHLIST"\|"OUT_OF_STOCK"}` | guest/customer | 201 `{pool, deduplicated}`. 422 `INVALID_DEMAND_QUERY`, 409 `LISTING_IN_STOCK`, 404 `LISTING_NOT_FOUND`, 403 for retailer/admin. Same person within 24 h → `deduplicated: true`. |
| `POST /demand/pools/{id}/join` `{pincode?}` | guest/customer | 404 `DEMAND_POOL_NOT_FOUND` if expired. |
| `GET /demand/pools?q&pincode` | public | Aggregate counts only. |
| `GET /demand/my-requests` | customer | Includes retailer `offers[]` (listing to buy). |
| `GET /retailer/demand-gaps?pincode&category_id` | retailer | Only pools ≥ admin threshold within the store's `service_pincodes`. |
| `POST /retailer/demand-gaps/{id}/fulfill` `{listing_id, note?}` | retailer | 403 `PINCODE_NOT_SERVICED`/`RETAILER_NOT_VERIFIED`, 404 listing not yours, 409 `ALREADY_RESPONDED`. Notifies requesters. |
| `GET /admin/demand/pools?status`, `PATCH /admin/demand/pools/{id}` `{status?, visibility_threshold?}`, `GET /admin/demand/trends?days` | admin | 409 `OPEN_POOL_EXISTS` when reopening a duplicate. |
UI: show “Request this product” on zero results (`components/phase3/request-product.tsx`) and “Notify me” on out-of-stock PDPs (`signal_type: OUT_OF_STOCK`). Zero-result searches are also logged automatically server-side.

### 3B Community Buying
| Endpoint | Role | Notes |
| :--- | :--- | :--- |
| `GET /community-buying/campaigns`, `GET /community-buying/campaigns/{id}` | public | `participants_needed`, `seconds_remaining`, `my_membership` when signed in. |
| `POST /community-buying/campaigns/{id}/join` `{quantity 1..10}` | customer | 409 `ALREADY_JOINED`/`CAMPAIGN_FULL`/`CAMPAIGN_CLOSED`/`INSUFFICIENT_STOCK`, 422 `QUANTITY_LIMIT`. No payment at join. |
| `POST …/{id}/leave` | customer | Only while OPEN. |
| `GET …/{id}/share` | customer | `{url, message, whatsapp_url, sms_url}`; share URL is `/community-buying/{id}?ref=…`. |
| `GET/POST /retailer/community-buying/campaigns`, `POST …/{id}/cancel` | retailer | Body `{listing_id, min_participants≥2, max_participants, discount_percent ≤90, duration_hours 1..336, max_quantity_per_member ≤10, title?}`. |
| `GET/POST /admin/community-buying/campaigns`, `POST …/{id}/cancel` | admin | |
Lifecycle: OPEN → SUCCESSFUL (min reached at expiry, or immediately when full) → member `AWARDED` → checks out normally → `PURCHASED`. FAILED/CANCELLED notify members (no charge).

### 3C Community Exchange (RFQ)
| Endpoint | Role | Notes |
| :--- | :--- | :--- |
| `POST /exchange/requests` `{title, delivery_pincode, budget_limit_paise?, items[1..20]{name, quantity 1..10, unit?, notes?}, bidding_hours 1..168}` | customer | |
| `GET /exchange/requests`, `GET /exchange/requests/{id}` | customer (own) | `bids[]` sorted by price, with `items_covered/items_requested`, ETA, rating. |
| `POST /exchange/requests/{id}/accept-bid` `{bid_id}` | customer | 409 `RFQ_CLOSED`/`BID_NO_LONGER_AVAILABLE`. Puts lines in the basket at bid prices (48 h). |
| `POST /exchange/requests/{id}/cancel` | customer | |
| `GET /retailer/exchange/requests` | retailer | Open requests in service area; competitors' bids hidden (`bids: null`, `my_bid`). |
| `POST /retailer/exchange/requests/{id}/bids` `{lines[{manifest_index, listing_id, unit_price_paise}], estimated_delivery_hours, notes?}` | retailer | Re-posting revises. 422 `BID_ABOVE_LIST_PRICE`/`BID_OVER_BUDGET`/`INVALID_BID_LINE`, 409 `INSUFFICIENT_STOCK`/`RFQ_CLOSED`, 403 `PINCODE_NOT_SERVICED`. |
| `DELETE /retailer/exchange/requests/{id}/bids` | retailer | Withdraw. |
| `GET /admin/exchange/requests?status` | admin | |

### 3D AI Negotiator (rule-bound assistant)
| Endpoint | Role | Notes |
| :--- | :--- | :--- |
| `POST /negotiate/start` `{target_price_paise?, max_budget_paise?, language?}` | customer | 400 `EMPTY_CART`, 429 `NEGOTIATION_LIMIT` (10/day), 422 `UNSUPPORTED_LANGUAGE`. `status: REJECTED` when no seller allows negotiation. |
| `POST /negotiate/counter-offer` `{session_id, proposed_price_paise}` | customer | 409 `CART_CHANGED`/`NEGOTIATION_CLOSED`/`MAX_ROUNDS_REACHED`. |
| `POST /negotiate/accept` `{session_id}` | customer | Returns `quote_id`, `quote_total_payable_paise`, `quote_expires_at`; continue with `POST /reservations {quote_id}`. |
| `GET /negotiate/sessions/{id}` | customer | |
| `GET/PUT /retailer/negotiation-rules`, `DELETE …/{id}` | retailer | `{listing_id?, min_floor_price_paise? (listing only), max_auto_discount_percent ≤50, bundle_quantity_threshold?, bundle_extra_discount_percent ≤20}`. |
UI: render `messages[]` as a chat; `language_fallback: true` means messages are in English (only `en`/`hi` templates exist). The floor price is never exposed.

### 3E Dukaan vs Dukaan
| Endpoint | Role | Notes |
| :--- | :--- | :--- |
| `POST /auctions/start` `{pincode}` | customer | Snapshots the current basket for 90 s. 409 `AUCTION_IN_PROGRESS`, 400 `EMPTY_CART`. |
| `GET /auctions/{id}/live` | customer (own) | JSON snapshot; or **SSE** with `Accept: text/event-stream` (events `auction` every 2 s, then `end`). Poll ≤ every 2 s otherwise. |
| `POST /auctions/{id}/accept` `{bid_id}` | customer | Only after the timer (409 `AUCTION_STILL_LIVE`). Switches the basket to the winning store at the bid price (30 min). |
| `POST /auctions/{id}/cancel` | customer | |
| `GET /retailer/auctions` | retailer | Only baskets the store can fully supply in its area; shows `best_bid_paise`, `my_best_bid_paise`, `my_list_total_paise`. |
| `POST /retailer/auctions/{id}/bid` `{bid_price_paise, delivery_eta_minutes 10..1440, warranty_note?}` | retailer | 422 `BID_ABOVE_LIST_PRICE`/`BID_NOT_LOWER`/`CANNOT_FULFIL_BASKET`, 409 `AUCTION_CLOSED`. |
| `GET /admin/auctions?status` | admin | |
Note: `EventSource` cannot send custom headers; cookie auth works (same-site). With bearer tokens use polling.

### 3F Price Intelligence
`GET /price-intelligence/listings/{listing_id}?days=7..90` (public): `lowest/highest/average_price_30d/90d_paise`, `current_vs_30d_average_pct`, `is_lowest_in_window`, `badge ∈ {GENUINE_DISCOUNT, MRP_INFLATED, NO_SPECIAL_DISCOUNT, INSUFFICIENT_HISTORY}`, `badge_reason`, `history[] {date, price_paise, day_low_paise, mrp_paise}`. Widget: `components/phase3/price-intelligence.tsx`. 404 for inactive listings/unverified stores.

### 3G Sale Stream (no Rewind)
`GET /sale-stream/live?event_type&category_slug&before&since&limit≤50` (public). Poll with `since = previous server_time` every `poll_after_seconds` (15). Items carry `deal_price_paise`, `old_price_paise`, `discount_pct`, live `stock_remaining`, `seconds_remaining`. Expired events are never returned (Sale Stream Rewind is permanently out of scope). FLASH_DEAL prices apply automatically at quote time via the underlying offer.

### 3H Bharat Multilingual
* UI strings: `frontend/locales/{en,hi,ta,te,kn,bn,mr,gu}.json`; `useI18n().t(key, vars)`; `<LanguageSwitcher/>`. Missing keys fall back to English. Non-English strings are a **seed set requiring native-speaker review**.
* `GET /i18n/languages`, `GET/PUT /i18n/preference` (auth), `GET /i18n/normalize?q=`, `GET /i18n/translations?entity_type=product|category|offer&lang=&ids=a,b` (≤100 ids) to overlay translated names/descriptions; admin `PUT /admin/i18n/translations`.
* Search accepts regional scripts/romanised terms directly.

### 3I Handwritten List to Basket (optional)
* `POST /vision/parse-list` with `{text}` **or** `{image_base64, content_type: image/jpeg|png|webp}` (≤5 MB, magic bytes checked). Returns `items[] {line, name, interpreted_as, size, quantity, candidates[], suggested_listing_id}`. **503 `OCR_PROVIDER_UNAVAILABLE`** when no OCR service is configured (current state) — show the typed-list fallback; never invent results.
* `POST /vision/build-cart {items[{listing_id, quantity}]}` → `{cart_id, added, skipped[]}`; 409 `NOTHING_TO_ADD`.

## 3. Pages delivered (functional, pre-redesign)
Customer: `/sale-stream`, `/community-buying`, `/community-buying/[id]`, `/exchange`, `/auctions`, `/list-to-basket`; PDP price history; cart negotiator; zero-result “Request this product”. Retailer: `/retailer/demand-gaps`, `/retailer/exchange`, `/retailer/auctions`, `/retailer/community-buying`, `/retailer/negotiation`. Admin: `/admin/demand`. All are intentionally plain so the redesign can restyle them without logic changes.
