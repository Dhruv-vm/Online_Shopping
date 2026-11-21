# Basket — Two-Laptop Demo Runbook

The host is this Mac. Laptop A is the **customer**, Laptop B is the **retailer**; either can
be the Mac itself. Run every command **in your own Terminal** on the Mac, from the repository
folder. Processes started by helper tools can stop when those tools restart.

## 1. Start (about 2 minutes the first time)
```bash
open -a Docker                      # Docker Desktop must be running
scripts/shared-demo.sh up
```
This does the following:
1. Starts Kafka and OpenSearch and waits for them to be healthy.
2. Creates `basket_shared_demo` from the demo seed if it is missing.
3. Applies migrations.
4. Starts the API on 127.0.0.1:8100.
5. Builds the frontend if needed and serves it on port 3100.

It prints the address to open.

## 2. Pick how the laptops connect
- **Same Wi-Fi (recommended, fully live):** both open `http://<Mac-LAN-IP>:3100`
  (printed by `up`, e.g. `http://10.115.28.176:3100`). If the page doesn't load, allow incoming
  connections for `node` in macOS Firewall.
- **Different networks:** `scripts/shared-demo.sh tunnel` prints `https://<words>.trycloudflare.com`.
  Updates arrive within about 10 s instead of about 1 s: Cloudflare quick tunnels do not deliver
  live streams, so pages refresh automatically. For fully live updates over the internet you
  need a named Cloudflare tunnel, which requires a Cloudflare account.

## 3. Accounts (password `Basket@123`)

| Role | Email |
|---|---|
| Customer (Laptop A) | `customer@basket.demo` |
| Second customer (for group buys) | `customer2@basket.demo` (demo account created for the two-client test) |
| Retailers (Laptop B) | `retailer1@basket.demo` (Basket Mart) … `retailer4@basket.demo` |
| Admin | `admin@basket.demo` |

## 4. Demo scenario (nothing needs a reload)

| # | Laptop B (retailer) | Laptop A (customer) sees |
|---|---|---|
| 1 | Retailer → Listings → New product | It appears in Products / search (~1 s) |
| 2 | Change a listing price | The product page shows the new price (~1 s) |
| 3 | Inventory → set stock to 0, then back | "Out of Stock from this Seller", then available again |
| 4 | Offers → new offer on a product in A's cart | The cart shows "Active Promotional Discounts" |
| 5 | (A) Cart → Dukaan vs Dukaan → start | Retailers 3 and 4 (Pigeon kettle) see the auction instantly |
| 6 | Retailer 3 bids, then retailer 4 bids lower | 3 shows **Outbid**, 4 shows **You are winning** (~1 s) |
| 7 | (A) Checkout → place order | Retailer → Orders lists it (~1 s) |
| 8 | Orders → seeded paid order `ORD-DEMO-A75E30` → Processing/Packed | A's order page updates (~1 s) |
| 9 | Community buying → new campaign; A joins | customer2's campaign page goes 0 → 1 of 2 |
| 10 | Try retailer URLs as A, or customer actions as B | Refused (403/404) |

The retailer **Auctions** page also has a labelled **Demo simulation** (browser-only, nothing
saved) with simulated stores, a countdown, winner/outbid and **Reset**.

Paying for an order needs a Razorpay test checkout. That is outside this demo; use the seeded
paid order for fulfilment.

## 5. Shut down
```bash
scripts/shared-demo.sh down        # data is kept
scripts/shared-demo.sh reset-db    # optional: restore the demo data
```

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Laptop can't open the URL | Same Wi-Fi? Mac firewall allows `node`? Use the IP printed by `up` (the IP changes between networks; run `up` again on a new network). |
| Clicking buttons gives "Cross-origin request forbidden" | The API doesn't know that address yet. Run `scripts/shared-demo.sh restart` (on a new LAN IP), or re-run `tunnel`. |
| No live updates on the LAN | Open DevTools → Network → `realtime/stream` should be 200 and pending. Check `scripts/shared-demo.sh status`. Pages still refresh on focus. |
| Search ignores a new product | The log should show `Kafka indexing active`; check consumer lag (see the Docker setup doc). Search falls back to PostgreSQL automatically. |
| Kafka/OpenSearch unhealthy | `docker compose -f deploy/docker-compose.shared-demo.yml ps`; Docker Desktop needs ~1.5 GB free. |
| Code changed | `scripts/shared-demo.sh restart` (rebuilds the frontend). |

Logs: `.shared-demo/api.log`, `.shared-demo/web.log`, `.shared-demo/tunnel.log`.
Repeatable checks:
- `scripts/shared-demo-live-check.py`
- `scripts/shared-demo-auction-check.py`
- `scripts/shared-demo-kafka-check.py`
- `scripts/shared-demo-intent-examples.py`
