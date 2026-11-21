# Basket — Shared Demo Test Report

**Date:** 21 Nov 2026
**Environment:** `scripts/shared-demo.sh` on the host Mac (Kafka + OpenSearch in Docker; API and
Next.js production build; database `basket_shared_demo`).
**Address:** `http://10.115.28.176:3100`, plus a Cloudflare quick tunnel.

## How it was tested
- Independent browser contexts (Playwright Chromium), each with its own cookies and session:
  - customer
  - second customer
  - retailer 1, retailer 3 and retailer 4
- All open on the LAN URL at the same time.
- Every write was sent with `fetch()` from inside that client's page, so the real Origin header,
  cookies and CSRF tokens applied, exactly as on a laptop.
- For each scenario the observing page was already open; the check waited for the change to appear
  **without a reload**. Navigation events were counted: zero in every case.

**Not tested: two physical laptops.** All clients ran on one Mac. Under the brief's wording these
are "independent client environments", not "two separate devices". Run the runbook on two real
laptops before presenting.

## Results: Part 4 / Part 17 scenarios

| # | Scenario | Result | Time to appear |
|---|---|---|---|
| 1 | Retailer adds product → customer sees it | PASS (no card before, card after) | 1.28 s |
| 2 | Retailer changes price → customer sees it | PASS | 0.53 s |
| 3 | Retailer updates stock → customer sees availability | PASS (Out of Stock, then back) | 1.30 s / 0.77 s |
| 4 | Retailer creates offer → customer sees it (cart discount) | PASS | 0.77 s |
| 5 | Auction starts → eligible retailers (3 and 4) see it | PASS | < 0.05 s |
| 6 | Retailer bids → other eligible retailer sees it; Outbid / Winning flip | PASS | 1.0–1.3 s |
| 7 | Customer creates order → retailer sees it | PASS | 1.04 s |
| 8 | Retailer fulfils (seeded paid order) → customer sees status | PASS | 0.77 s |
| 9 | Group buy: customer joins → second customer sees 0 → 1 of 2 | PASS | 0.53 s |
| 10 | Restricted actions across roles | PASS: 6 probes refused (403 ×4, 404 ×2) | — |
| — | Both clients connected during simultaneous use | PASS: 8–9 concurrent live connections (`/realtime/status`) | — |
| — | Tunnel client sees a LAN retailer's change | PASS via fallback (no SSE over quick tunnels) | 5.7 s |
| — | Browser writes from the tunnel origin | PASS (200) | — |

## Defects found and fixed during this test
1. **Every browser write from the LAN or tunnel address was rejected** (`CSRF_ORIGIN_INVALID`):
   the origin allow-list only had localhost. The demo script now passes the exact demo origins.
   This would have broken add-to-cart, checkout, bids and joins on real laptops.
2. **Cloudflare quick tunnels don't deliver SSE.** The client now detects a silent stream and
   refreshes every 10 s.
3. **`shared-demo.sh tunnel` exited silently** (`set -e` with `pipefail` on a grep that hadn't
   matched yet). Fixed; it also restarts the API for the tunnel origin.
4. **`shared-demo.sh down` stopped nothing** (`set -e` on a missing pid file). Fixed.
5. Live-scenario setup hit real business rules, which behaved correctly:
   - stock cannot be set below reserved units (409);
   - only paid orders can be fulfilled (the seeded paid order was used).

## Also verified on the shared demo
- **Kafka/OpenSearch:** see the Kafka report.
- **Intent examples:** see the intent guide.
- **Coupon states** on live quotes:
  - MART10 applied: −₹69.90 on ₹699;
  - not applicable on another store;
  - `INVALID_DISCOUNT_CODE` for an unknown code.
- **Dukaan vs Dukaan** full live auction: started, bid, outbid, closed by itself; one close
  notice per store.

## Demo data changes made by the tests
- Demo account `customer2@basket.demo` was created.
- Seeded order `ORD-DEMO-A75E30` advanced to PACKED for retailer 1's items.
- A few test orders were left PENDING_PAYMENT; they expire on their own.
- Test products "Demo Live Tea …" were deactivated; test offers were deactivated; test campaigns
  were cancelled.
- Prices and stock were restored.

`scripts/shared-demo.sh reset-db` restores the original demo data.
