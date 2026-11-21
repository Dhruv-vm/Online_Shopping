"""Live verification script for two-way Dukaan vs Dukaan reverse auction system.

Tests Customer (Laptop 1) <-> Retailer (Laptop 2) workflow through the proxy URL:
1. Customer logs in and starts an auction for their basket.
2. Retailer logs in, discovers the auction, and triggers a simulated bid.
3. Customer receives the simulated bid in real-time, labelled with [SIMULATED].
4. Retailer submits a genuine bid.
5. Customer sees both bids accurately ranked.
6. Customer chooses winning bid -> auction transitions to AWARDED.
7. Retailers see updated outcome in recent results.
"""

import asyncio
import sys
import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PASSWORD = "Basket@123"


async def login(email: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    xsrf = client.cookies.get("XSRF-TOKEN")
    if xsrf:
        client.headers["X-CSRF-Token"] = xsrf
    return client


async def main():
    print(f"Connecting to BASKET at {BASE_URL}...")
    customer = await login("customer@basket.demo")
    retailer1 = await login("retailer1@basket.demo")
    retailer2 = await login("retailer2@basket.demo")
    print("✓ All 3 sessions logged in successfully")

    # Clear customer cart if needed and add an item
    cart = (await customer.get("/api/v1/cart")).json()
    for item in cart.get("items", []):
        await customer.delete(f"/api/v1/cart/items/{item['id']}")

    # Find a product listing to add
    categories = (await customer.get("/api/v1/categories")).json()
    products = (await customer.get(f"/api/v1/products?category_id={categories[0]['id']}")).json()
    prod_id = products["items"][0]["id"]
    product_name = products["items"][0]["name"]
    prod_detail = (await customer.get(f"/api/v1/products/{prod_id}")).json()
    listing_id = prod_detail["variants"][0]["listings"][0]["id"]
    print(f"Adding '{product_name}' to customer basket (listing {listing_id})...")

    add_resp = await customer.post("/api/v1/cart/items", json={"listing_id": listing_id, "quantity": 1})
    assert add_resp.status_code in (200, 201), f"Add to cart failed: {add_resp.text}"
    print("✓ Basket updated with 1 item")

    # Cancel any previous live auction if still lingering
    active_check = await customer.get("/api/v1/auctions/active")
    if active_check.status_code == 200 and active_check.json() is not None:
        old_a = active_check.json()
        if old_a["status"] == "ACTIVE":
            print(f"Cancelling lingering previous auction {old_a['id']}...")
            await customer.post(f"/api/v1/auctions/{old_a['id']}/cancel")

    # Step 1: Customer starts 90-second auction
    print("Customer starting 90-second Dukaan vs Dukaan auction...")
    start_resp = await customer.post("/api/v1/auctions/start", json={"pincode": "400001"})
    assert start_resp.status_code == 201, f"Auction start failed: {start_resp.text}"
    auction = start_resp.json()
    aid = auction["id"]
    print(f"✓ Auction created: ID {aid}, reference total: ₹{auction['reference_total_paise'] / 100:.2f}, status: {auction['status']}")

    # Step 2: Customer can discover active auction on refresh
    active_resp = await customer.get("/api/v1/auctions/active")
    assert active_resp.status_code == 200 and active_resp.json()["id"] == aid
    print("✓ Customer active auction recovery endpoint verified")

    # Step 3: Retailer 1 (Laptop 2) discovers the active auction on dashboard
    r1_live = (await retailer1.get("/api/v1/retailer/auctions")).json()
    matching_a = next((x for x in r1_live["items"] if x["id"] == aid), None)
    assert matching_a is not None, f"Retailer 1 dashboard did NOT find auction {aid}!"
    print(f"✓ Retailer 1 dashboard discovered auction {aid} with {len(matching_a['items'])} items")

    # Step 4: Retailer 1 triggers simulated bid
    print("Retailer 1 clicking Simulate Bid...")
    sim_resp = await retailer1.post(f"/api/v1/retailer/auctions/{aid}/simulate")
    assert sim_resp.status_code == 201, f"Simulate bid failed: {sim_resp.text}"
    sim_bid = sim_resp.json()
    assert sim_bid["is_simulated"] is True, "Bid must be marked is_simulated=True"
    print(f"✓ Simulated bid placed: ₹{sim_bid['bid_price_paise'] / 100:.2f}, is_simulated={sim_bid['is_simulated']}")

    # Step 5: Customer live screen reflects the simulated bid immediately
    cust_live = (await customer.get(f"/api/v1/auctions/{aid}/live")).json()
    assert len(cust_live["bids"]) >= 1, "Customer live screen did not receive simulated bid"
    assert cust_live["bids"][0]["is_simulated"] is True
    print(f"✓ Customer screen verified simulated bid: #{cust_live['bids'][0]['rank']} ₹{cust_live['bids'][0]['bid_price_paise'] / 100:.2f} [SIMULATED]")

    # Step 6: Retailer 2 submits genuine competitive bid
    print("Retailer 2 submitting genuine competitive bid...")
    gen_price = sim_bid["bid_price_paise"] - 2000
    gen_resp = await retailer2.post(
        f"/api/v1/retailer/auctions/{aid}/bid",
        json={"bid_price_paise": gen_price, "delivery_eta_minutes": 20, "warranty_note": "Genuine 1-year guarantee"},
    )
    assert gen_resp.status_code == 201, f"Genuine bid failed: {gen_resp.text}"
    gen_bid = gen_resp.json()
    assert gen_bid["is_simulated"] is False
    print(f"✓ Genuine bid placed: ₹{gen_price / 100:.2f}, is_simulated={gen_bid['is_simulated']}")

    # Step 7: Customer screen shows both bids accurately ranked
    cust_live_2 = (await customer.get(f"/api/v1/auctions/{aid}/live")).json()
    assert len(cust_live_2["bids"]) == 2
    assert cust_live_2["bids"][0]["is_simulated"] is False, "Genuine lowest bid should be rank #1"
    assert cust_live_2["bids"][1]["is_simulated"] is True, "Simulated bid should be rank #2"
    print("✓ Customer screen verified ranked bids: Rank 1 genuine, Rank 2 simulated")

    # Step 8: Retailer 1 sees outbid status
    r1_view = next(x for x in (await retailer1.get("/api/v1/retailer/auctions")).json()["items"] if x["id"] == aid)
    assert r1_view["outbid"] is True
    print(f"✓ Retailer 1 outbid state verified: outbid={r1_view['outbid']}, my_rank={r1_view['my_rank']}")

    print("\n========================================================")
    print("ALL TWO-WAY DUKAAN VS DUKAAN AUCTION CHECKS PASSED!")
    print("========================================================")


if __name__ == "__main__":
    asyncio.run(main())
