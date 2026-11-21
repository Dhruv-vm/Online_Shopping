# Basket — Cache Audit and Fix Report

## Inventory of every cache layer

| Layer | Finding | Action |
|---|---|---|
| Next.js page rendering | All 60+ routes are dynamic (`ƒ` in the build output); none is prerendered with data | none needed |
| Next.js server fetch | `apiClient` uses `cache: "no-store"`; `/categories` and `/retailers` set `revalidate = 0` | none needed |
| **Server-rendered pages in same-origin mode** | **Bug:** on the shared demo the server-side API base was empty, so `/categories` and `/retailers` rendered with no data | **Fixed:** the server calls `BASKET_API_PROXY_TARGET` |
| **HTTP caching of API responses** | **Gap:** no `Cache-Control` on JSON. Per-user data (cart, orders, notifications) passes through a Cloudflare tunnel and the Next proxy | **Fixed:** middleware sets `private, no-store` on `/api/*` unless an endpoint sets its own (SSE keeps `no-cache`). Test: `test_final_cache_headers.py` |
| Next.js rewrite proxy | Pass-through, `compress: false` (keeps the SSE stream unbuffered on the LAN) | none needed |
| Frontend client state | No query library. Pages refetch through `useLoad`/loaders; live notices trigger quiet refetches | live updates added (see realtime report) |
| Browser storage | `localStorage`: language, recently viewed, compare list, location. `sessionStorage`: checkout coupon (new). No prices or stock are stored | none needed |
| Backend in-memory | Only `index_health._cache` (search-engine decision, short TTL) | none needed |
| **Search index** | **Bug:** in Kafka mode the indexer never consumed and the index was never built, so search either used PostgreSQL or a missing index | **Fixed:** see the Kafka report. A price change now reaches OpenSearch in about 1.2 s |
| Static media `/media` | `StaticFiles` with ETag/Last-Modified; uploads get unique names | none needed |
| Redis / CDN | Not used | — |

## Stale-data checks done live
- Price, stock and offer changes were visible on open customer pages within 0.5–1.3 s, without reload.
- A cart re-quotes automatically when an offer or price changes, and checkout prices always
  come from a fresh server quote.
