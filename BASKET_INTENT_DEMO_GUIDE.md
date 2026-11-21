# Basket — Customer Intent Demo Guide

Where: **Account → Shopping intent** (`/account/intent`), card **"Tell Basket what you want to buy"**.
Sign in as `customer@basket.demo` / `Basket@123` on the shared demo (`scripts/shared-demo.sh up`).

Everything shown comes from real data in the database the app is using. The workflow
never invents matches, stores or notifications. Results below were produced on
`basket_shared_demo` on 2026-11-21 (`scripts/shared-demo-intent-examples.py` re-runs them).

## What happens when you press "Save intent"

| # | Step | How |
|---|------|-----|
| 1 | Intent saved | Row in `customer_recurring_intentions` (items, budget, frequency, PIN, buy-by date). |
| 2 | What we understood | Each item, quantity, specs, budget, frequency, PIN and date are echoed back ("Understood: …"). |
| 3 | Category and products | Catalogue search (OpenSearch, or the PostgreSQL fallback). Every word typed must match a whole word in the product's name, brand or category. The category shown is the matched product's. |
| 4 | Real listings | Active listings from **verified, active** stores that **serve the PIN** and have **enough stock** for the quantity; cheapest first (top 3). For a single-item intent the budget is a price ceiling per unit. Live code-free offers on the listing are named. |
| 5 | Demand Gap | Each item with no qualifying listing becomes a `WISHLIST` signal through the existing Demand Gap service (pool per product name + PIN). |
| 6 | Stores / pools | "N store(s) can supply" counts distinct qualifying stores. For gaps: the pool's shopper count and whether stores can see it yet (visibility threshold, default 2). |
| 7 | Status | `MATCHED` (all items available), `PARTIALLY_MATCHED`, or `WAITING_FOR_SUPPLY`. |
| 8 | Next steps | Create a basket, budget advice, how demand is handled, and the repeat schedule. |
| 9 | Review / update | "Your intents" → **Review** reloads it into the form; **Update intent** saves changes and re-matches. **Refresh status** re-matches without recording new demand. |
| 10 | No duplicates | Resubmitting the same items + PIN + frequency updates the existing intent (`updated_existing: true`). Demand signals are deduplicated per shopper per pool for 24 h; viewing never records demand. |

**Create basket** adds the cheapest qualifying listing for each available item to the cart
at the requested quantity; unavailable items are listed as skipped. Checkout is then the
normal flow (quote → reservation → payment).

**When a matching listing becomes available:** a store responds to the pool from
**Retailer → Demand gaps** and fulfils it with a listing. Every shopper who signalled that
pool then receives the in-app notification **"Now available near you"** (bell icon).
This is the existing Demand Gap fulfilment, not something added for the demo.

## Example A — Monthly groceries

Form values:

| Field | Value |
|---|---|
| Name | `Monthly groceries` |
| Delivery PIN | `560034` |
| Budget ₹ | `4000` |
| How often | Monthly |
| Items | `Rice` ×1 · `Atta` ×1 · `Cooking oil` ×1 · `Dal` ×2 |

Expected screen (demo data):
- Badge **Intent saved** · "Some items are available; the rest are recorded as demand" (`PARTIALLY_MATCHED`).
- **Rice**: Grocery & Food · 2 store(s) can supply · cheapest *Premium Royal Basmati Rice 5kg · Basket Mart · ₹699.00*.
- **Atta, Cooking oil, Dal**: "Not available near you". The demo catalogue has no atta or dal, and its only oil is olive oil, which "cooking oil" does not match. Each shows *Demand Gap "…": 1 shopper(s) · stores see it at 2 · your request was added*.
- Cheapest matching basket **₹699.00 · within budget**; **Create basket** button.
- Next steps: create a basket; unavailable items recorded in Demand Gaps; "This intent repeats monthly…".

Demand aggregation: sign in as a **second customer** and submit the same items with PIN
`560034`. Each pool reaches 2 shoppers, the screen says "visible to stores", and the pools
appear for retailers under **Retailer → Demand gaps**.

## Example B — Laptop

| Field | Value |
|---|---|
| Name | `New laptop` |
| Delivery PIN | `560034` |
| Budget ₹ | `60000` |
| How often | One time |
| Buy by | `2026-12-31` |
| Items | `Laptop` ×1, specs `16GB RAM, 512GB SSD, for work` |

Expected: **Everything is available near you** (`MATCHED`). Understood as *Laptop (16GB RAM,
512GB SSD, for work)* · Electronics · 2 store(s) · cheapest *Dell Inspiron 15 Core i5 16GB RAM
512GB SSD Laptop · Namma Digital Store · ₹52,585.99*. Laptops above ₹60,000 are excluded.
Live offers on a listing are named next to it (none were live on these listings at the time).
Specs are shown and stored; matching is by product name and the budget ceiling. Specs are not
parsed into filters.

## Example C — Unavailable product

| Field | Value |
|---|---|
| Name | `Standing desk` |
| Delivery PIN | `560034` |
| How often | One time |
| Items | `Electric standing desk` ×1 |

Expected: **Not available near you yet — recorded as demand** (`WAITING_FOR_SUPPLY`).
Demand Gap *"Electric standing desk": 1 shopper(s) · stores see it at 2 · your request was added*.
No Create basket button. Next step explains the in-app notification when a store lists it.
Press **Save intent** again: badge **Intent updated** and "your request was already counted".

## APIs (all under `/api/v1`, customer session; writes need the CSRF header)

| Method | Path | Purpose |
|---|---|---|
| POST | `/intent/workflow` | Save (or update a duplicate) and analyse. 201. |
| GET | `/intent/workflow` | List your intents with last status. |
| GET | `/intent/workflow/{id}` | Re-analyse; never records demand. 404 for another customer's intent. |
| PUT | `/intent/workflow/{id}` | Update and re-analyse. |
| POST | `/intent/workflow/{id}/basket` | Add cheapest qualifying listings to the cart. 409 `NOTHING_TO_ADD` if none. |

Request body: `{title, items:[{name, quantity, specs?}], budget_paise?, frequency: ONCE|WEEKLY|BIWEEKLY|MONTHLY|QUARTERLY|SEASONAL|CUSTOM, pincode?, purchase_by?, notes?}`.

## Database effects

- `customer_recurring_intentions` (migration `0036_intent_workflow`, additive): `items`, `pincode`,
  `purchase_by`, `dedupe_key` (sha-256 of sorted item names + PIN + frequency; indexed with
  `customer_id`), `last_analysis`, `analyzed_at`. After the three examples (twice each) there are **3 rows**.
- `demand_pools` / `demand_signals`: one OPEN pool per (item, PIN) — *Atta, Cooking oil, Dal,
  Electric standing desk* @ 560034 — each with **1 signal** after two submissions.
  `demand.pool_created` events go through the outbox (no PIN in the event).
- `carts` / `cart_items`: only after **Create basket**.

## Tests

`backend/tests/test_final_intent_workflow.py` covers:
- real matches only, and stores outside the PIN are excluded;
- the budget ceiling;
- an update instead of a duplicate, with one signal per item;
- viewing records nothing;
- the basket contents;
- one customer cannot read another's intent.
