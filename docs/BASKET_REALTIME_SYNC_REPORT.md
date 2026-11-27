# Basket — Real-time Sync Report

## What was built
- **Backend hub** (`backend/app/modules/realtime/`):
  - Endpoint `GET /api/v1/realtime/stream`: authenticated Server-Sent Events.
    Sends `ready`, then `change` notices `{type, entity, id, at}`, with a keep-alive every 15 s.
  - Endpoint `GET /realtime/status`: connection, published and delivered counters.
  - Bounded per-connection queue (200; the oldest notice is dropped when full).
  - Fed by a per-instance Kafka consumer group in Kafka mode, or by the direct dispatcher in direct mode.
- **New outbox events** (marketplace topic, no PII):
  - `fulfilment.status_changed`
  - `group_buy.member_joined` and `group_buy.member_left`
  - `auction.closed`
  - `offer.created` and `offer.updated`
- **Frontend** `lib/realtime.ts`:
  - One EventSource per tab, opened only when signed in, with reconnect backoff.
  - `useLiveUpdates(prefixes, refetch)`: debounced 250 ms, refreshes on focus, with a fallback
    interval (60 s while live, 10 s while the stream is unavailable).
  - `useLiveState()` drives the "Live updates on" indicator.
  - Background refetches don't flash the loading state.
- **Wired pages:**
  - products list and detail, cart (re-quotes), orders list and detail
  - retailer dashboard, orders, listings, inventory, offers, auctions
  - community buying (list, detail, retailer), and the notification bell
- **Retailer notifications** (D2) through the existing in-app notifications:
  - new RFQ in the store's area
  - new auction the store can fully supply
  - auction closed (to bidders)
  - won / not selected
  - paid order

## Verified (21 Nov 2026, shared demo on `http://10.115.28.176:3100`)
Measured in independent browser contexts (separate cookies) on the same Mac. Every write was
sent from inside the browser page, so real Origin and CSRF checks applied. No page was
reloaded in any case.

| Scenario | Seen by the other client after |
|---|---|
| New retailer product in the customer's product list | 1.28 s |
| Price change on the product page | 0.53 s |
| Stock to zero → "Out of Stock", and back | 1.30 s / 0.77 s |
| New offer → "Active Promotional Discounts" in the cart | 0.77 s |
| Customer order on the retailer's orders page | 1.04 s |
| Fulfilment status on the customer's order page | 0.77 s |
| New auction on two eligible retailers' pages | < 0.05 s |
| Competing bid → other store sees it; Outbid / Winning flip | 1.0–1.3 s |
| Customer joins group buy → second customer's page 0 → 1 of 2 | 0.53 s |
| Backend round trip (retailer write → customer SSE), scripted | 0.9–1.1 s |
| Over the Cloudflare quick tunnel (stream not delivered, polling fallback) | 5.7 s |

**Not done:** a test on two physical laptops. The two-client checks used independent client
environments on one machine. Please confirm on two real devices with the runbook before calling it
verified for your presentation.

## Known limits
- Cloudflare **quick** tunnels do not deliver SSE; tunnel users get ≤ 10 s refresh instead.
- Notices are at-most-once. A client that is offline when a notice is sent catches up on its
  next refresh (focus or interval); nothing is lost on the server.
