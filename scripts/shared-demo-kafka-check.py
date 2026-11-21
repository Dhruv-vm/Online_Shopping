"""Kafka + OpenSearch live check on the shared demo (restores what it changes)."""
import json, subprocess, sys, time
import httpx

BASE = "http://127.0.0.1:3100"
OS = "http://127.0.0.1:9201"
c = httpx.Client(base_url=BASE, timeout=30)
c.post("/api/v1/auth/login", json={"email": "retailer1@basket.demo", "password": "Basket@123"}).raise_for_status()
c.headers["X-CSRF-Token"] = c.cookies.get("XSRF-TOKEN", "")

listings = c.get("/api/v1/retailer/listings").json()["items"]
lst = next(x for x in listings if x.get("is_active"))
lid, old = lst["id"], lst["selling_price_paise"]
name = lst.get("product_name") or lst.get("variant", {}).get("product", {}).get("name")
new = old - 100 if old > 1000 else old + 100
print(f"listing {lid} '{name}': ₹{old/100:.2f} -> ₹{new/100:.2f}")

def os_price(product_name):
    q = {"query": {"match_phrase": {"name": product_name}}, "size": 1}
    r = httpx.post(f"{OS}/basket_*_products_search/_search", json=q).json()
    hits = r["hits"]["hits"]
    return hits[0]["_source"].get("min_price_paise") if hits else None

before = os_price(name)
t0 = time.monotonic()
r = c.patch(f"/api/v1/retailer/listings/{lid}", json={"selling_price_paise": new})
if r.status_code == 405:
    r = c.put(f"/api/v1/retailer/listings/{lid}", json={"selling_price_paise": new})
print("price update:", r.status_code)
seen = None
for _ in range(60):
    p = os_price(name)
    if p is not None and p != before:
        seen = time.monotonic() - t0
        break
    time.sleep(0.5)
print(f"OpenSearch min_price before={before} after={os_price(name)} (updated in {seen:.2f}s)" if seen else "OpenSearch NOT updated within 30s")
s = httpx.get(f"http://127.0.0.1:8100/api/v1/search", params={"q": name, "page_size": 1}).json()
print("search API engine:", s["engine"], "| price shown:", s["items"][0]["min_price_paise"] if s["items"] else None)
r = c.patch(f"/api/v1/retailer/listings/{lid}", json={"selling_price_paise": old})
if r.status_code == 405:
    r = c.put(f"/api/v1/retailer/listings/{lid}", json={"selling_price_paise": old})
print("restored:", r.status_code)
time.sleep(4)
print("OpenSearch after restore:", os_price(name))
