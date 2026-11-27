# Basket — Shared Two-Laptop Demo Architecture

Laptop A (customer) and Laptop B (retailer) open **one address**. Both talk to the same
frontend, backend, PostgreSQL database, Kafka and OpenSearch, all running on the host Mac.

```
 Laptop A ─┐                        ┌─ Next.js 15 (production build, .next-shared)  :3100  (0.0.0.0)
 Laptop B ─┼─ http://<LAN-IP>:3100 ─┤    /api/v1/*  and /media/*  ──rewrite──▶ FastAPI  127.0.0.1:8100
 (or https://<name>.trycloudflare.com via cloudflared → localhost:3100)
                                    └─ everything else: pages
 FastAPI 127.0.0.1:8100 ── PostgreSQL 16 (Homebrew) database basket_shared_demo
                       ├── Kafka 3.7 (Docker, KRaft)   127.0.0.1:9094
                       └── OpenSearch 2.13 (Docker)     127.0.0.1:9201
```

## Why one entry point
- **Same origin for the browser.** Pages and `/api/v1` share one host, so the HttpOnly session
  cookie and the `XSRF-TOKEN` double-submit cookie work without cross-site settings.
  `NEXT_PUBLIC_API_URL=same-origin` makes the browser call relative `/api/v1/…`.
  Server-rendered pages call the proxy target directly.
- **Only port 3100 is exposed.** The API (8100), Kafka (9094) and OpenSearch (9201) listen on
  127.0.0.1 only; from the LAN they are refused (verified with `nc`). There is no public
  database or admin port.
- **The same URL works for LAN and tunnel.** The backend's CSRF/CORS origin list is generated
  from the LAN address and, when started, the tunnel URL.

## Data flow for a live change
1. A retailer action (price, stock, offer, bid, fulfilment, …) commits its row together with an
   **outbox event**, in the same transaction.
2. The outbox publisher sends it to Kafka (`basket.events.{orders,payments,catalogue,inventory,marketplace}`).
3. Consumers:
   - **order projection**;
   - **OpenSearch indexer**, which keeps search in sync;
   - a per-instance **realtime listener** that hands each event to the in-process hub.
4. The hub works out who may know about it (the role-aware audience below) and pushes an
   ids-only notice `{type, entity, id, at}` over `GET /api/v1/realtime/stream`
   (Server-Sent Events, authenticated by the session cookie).
5. The browser's `useLiveUpdates` hook matches the notice type and **refetches through the
   normal authorised API**. No data rides on the stream, so permissions are enforced as usual.
6. **Fallbacks:**
   - refresh on tab focus;
   - a safety-net refresh every 60 s while live, or every 10 s when the stream is unavailable
     (signed out, or a Cloudflare quick tunnel, which does not deliver SSE).

## Audience rules (hub)

| Event family | Who is notified |
|---|---|
| product, catalogue, listing, variant, inventory, price, sale_stream, offer | everyone signed in |
| order, payment, fulfilment | the order's customer and the retailers with items in it |
| auction | the auction's customer and retailers |
| group_buy | customers and the campaign's retailer |
| exchange | the request's customer and retailers |
| demand | retailers |
| negotiation | the session's customer |
| anything else | admins only (admins receive all) |

## Separation from your data
- Database `basket_shared_demo` (the name must end in `_demo`). **`basket_db` is never used.**
- Search index prefix `basket_basket_shared_demo_<hash>`, which is per database.
- Separate Next build directory `.next-shared`, and separate ports 3100/8100, so your own dev
  servers on 3000/8000 keep running.
