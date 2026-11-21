"""Two independent cookie sessions against the shared demo URL; measures live-notice latency."""
import asyncio, json, sys, time
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://10.115.28.176:3100"
PW = "Basket@123"

async def login(email):
    c = httpx.AsyncClient(base_url=BASE, timeout=30)
    r = await c.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, (email, r.status_code, r.text[:200])
    assert "access_token" in c.cookies, "no HttpOnly session cookie set through the proxy"
    tok = c.cookies.get("XSRF-TOKEN")
    if tok:
        c.headers["X-CSRF-Token"] = tok  # same double-submit the browser client does
    return c

async def main():
    cust = await login("customer@basket.demo")
    ret = await login("retailer1@basket.demo")
    anon = httpx.AsyncClient(base_url=BASE, timeout=10)
    print("anonymous stream:", (await anon.get("/api/v1/realtime/stream")).status_code)
    got = asyncio.get_event_loop().create_future()
    ready = asyncio.Event()
    async def listen():
        async with cust.stream("GET", "/api/v1/realtime/stream", timeout=None) as s:
            print("stream:", s.status_code, s.headers.get("content-type"))
            ev = None
            async for line in s.aiter_lines():
                if line.startswith("event:"): ev = line[6:].strip()
                if line.startswith("data:"):
                    if ev == "ready": ready.set()
                    elif ev == "change":
                        d = json.loads(line[5:])
                        if d["type"].startswith("offer.") and not got.done():
                            got.set_result(d); return
    t = asyncio.create_task(listen())
    await asyncio.wait_for(ready.wait(), 10)
    offers = (await ret.get("/api/v1/retailer/offers")).json()
    items = offers.get("items", offers) if isinstance(offers, dict) else offers
    t0 = time.monotonic()
    if items:
        o = items[0]
        r = await ret.put(f"/api/v1/retailer/offers/{o['id']}", json={"is_active": bool(o["is_active"])})
    else:
        r = await ret.post("/api/v1/retailer/offers", json={"name": "Live check offer", "discount_type": "PERCENTAGE", "discount_value": 500, "min_order_paise": 0, "is_active": False})
    print("retailer offer write:", r.status_code, r.text[:200])
    d = await asyncio.wait_for(got, 20)
    print(f"customer received {d['type']} id={d['id']} after {time.monotonic()-t0:.2f}s; keys={sorted(d)}")
    t.cancel()
    print("status:", (await cust.get("/api/v1/realtime/status")).text[:200])

asyncio.run(main())
