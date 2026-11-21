"""Dukaan vs Dukaan through the shared demo URL with three independent sessions.

Uses the demo database only (basket_shared_demo). Leaves one finished auction
behind and removes the item it put in the demo customer's cart.
"""
import asyncio, json, sys, time
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://10.115.28.176:3100"
LISTING = sys.argv[2]  # a listing whose variant other stores also stock
STORE_A = sys.argv[3] if len(sys.argv) > 3 else "retailer3@basket.demo"
STORE_B = sys.argv[4] if len(sys.argv) > 4 else "retailer4@basket.demo"
PW = "Basket@123"

async def login(email):
    c = httpx.AsyncClient(base_url=BASE, timeout=30)
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, (email, r.text[:200])
    c.headers["X-CSRF-Token"] = c.cookies.get("XSRF-TOKEN", "")
    return c

class Listener:
    def __init__(self, client, name):
        self.c, self.name, self.notices, self.ready = client, name, [], asyncio.Event()
    async def run(self):
        async with self.c.stream("GET", "/api/v1/realtime/stream", timeout=None) as s:
            ev = None
            async for line in s.aiter_lines():
                if line.startswith("event:"): ev = line[6:].strip()
                elif line.startswith("data:"):
                    if ev == "ready": self.ready.set()
                    elif ev == "change": self.notices.append((time.monotonic(), json.loads(line[5:])))
    async def wait_for(self, typ, aid, since, timeout=15):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for t, n in self.notices:
                if t >= since and n["type"] == typ and n["id"] == aid:
                    return t - since
            await asyncio.sleep(0.1)
        raise AssertionError(f"{self.name}: no {typ} for {aid}")

async def view(c, aid):
    items = (await c.get("/api/v1/retailer/auctions")).json()["items"]
    return next((x for x in items if x["id"] == aid), None)

async def main():
    cust, r1, r3 = await login("customer@basket.demo"), await login(STORE_A), await login(STORE_B)
    L1, L3 = Listener(r1, STORE_A), Listener(r3, STORE_B)
    tasks = [asyncio.create_task(L.run()) for L in (L1, L3)]
    await asyncio.gather(L1.ready.wait(), L3.ready.wait())

    added = await cust.post("/api/v1/cart/items", json={"listing_id": LISTING, "quantity": 1})
    assert added.status_code in (200, 201), added.text
    t0 = time.monotonic()
    a = await cust.post("/api/v1/auctions/start", json={"pincode": "400001"})
    assert a.status_code == 201, a.text
    aid = a.json()["id"]
    print(f"auction.started reached store A in {await L1.wait_for('auction.started', aid, t0):.2f}s, store B in {await L3.wait_for('auction.started', aid, t0):.2f}s")
    v1, v3 = await view(r1, aid), await view(r3, aid)
    assert v1 and v3 and v1["items"] == v3["items"], "both stores must see the same auction"
    print("both see:", [f"{i['quantity']}x {i['product_name']}" for i in v1["items"]], "PIN", v1["pincode"], "secs", v1["seconds_remaining"])

    p1 = v1["my_list_total_paise"] - 500
    t0 = time.monotonic()
    assert (await r1.post(f"/api/v1/retailer/auctions/{aid}/bid", json={"bid_price_paise": p1, "delivery_eta_minutes": 30})).status_code == 201
    print(f"store A bid seen by store B in {await L3.wait_for('auction.bid_placed', aid, t0):.2f}s")
    v1, v3 = await view(r1, aid), await view(r3, aid)
    print("after r1 bid → r1:", v1["my_rank"], "winning" if v1["is_winning"] else "", "| r3 sees best", v3["best_bid_paise"], "stores", v3["competing_stores"])
    assert v1["is_winning"] and v3["best_bid_paise"] == p1 and v3["my_rank"] is None

    p3 = min(p1, v3["my_list_total_paise"]) - 700
    t0 = time.monotonic()
    assert (await r3.post(f"/api/v1/retailer/auctions/{aid}/bid", json={"bid_price_paise": p3, "delivery_eta_minutes": 20})).status_code == 201
    print(f"store B bid seen by store A in {await L1.wait_for('auction.bid_placed', aid, t0):.2f}s")
    v1, v3 = await view(r1, aid), await view(r3, aid)
    print("after r3 bid → r1 outbid:", v1["outbid"], "rank", v1["my_rank"], "| r3 winning:", v3["is_winning"])
    assert v1["outbid"] and v1["my_rank"] == 2 and v3["is_winning"]
    assert all(set(x) == {"price_paise", "at", "mine"} for x in v1["bid_ladder"]) and v1["bids"] is None

    wait = v1["seconds_remaining"] + 1
    print(f"waiting {wait}s for the auction to close on its own...")
    t0 = time.monotonic() + wait - 1
    await asyncio.sleep(wait)
    d = await L1.wait_for("auction.closed", aid, t0 - 2, timeout=40)
    print(f"auction.closed reached store A {d:.1f}s after the deadline")
    o1 = next(x for x in (await r1.get("/api/v1/retailer/auctions/recent")).json()["items"] if x["id"] == aid)
    o3 = next(x for x in (await r3.get("/api/v1/retailer/auctions/recent")).json()["items"] if x["id"] == aid)
    print("outcomes:", o1["my_outcome"], o3["my_outcome"], "| lowest", o3["best_bid_paise"], "== r3 bid", p3)
    assert o1["my_outcome"] == o3["my_outcome"] == "AWAITING_CHOICE" and o3["best_bid_paise"] == p3
    for name, c in ((STORE_A, r1), (STORE_B, r3)):
        ns = (await c.get("/api/v1/notifications")).json()["items"]
        msgs = [n["event_type"] for n in ns if n["event_type"].startswith("retailer.auction")]
        print(name, "auction notices:", {k: msgs.count(k) for k in set(msgs)})
    closed_count = [x for x in L1.notices if x[1]["type"] == "auction.closed" and x[1]["id"] == aid]
    print("auction.closed notices on store A stream:", len(closed_count))
    assert len(closed_count) == 1
    cart = (await cust.get("/api/v1/cart")).json()
    for it in cart.get("items", []):
        if it.get("listing_id") == LISTING:
            await cust.delete(f"/api/v1/cart/items/{it['id']}")
    for t in tasks: t.cancel()
    print("OK")

asyncio.run(main())
