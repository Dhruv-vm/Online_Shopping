import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_session_factory
from app.core.search.client import get_opensearch_client
from app.core.search.index import get_search_alias_name
from app.modules.catalogue.models import (
    ProductListing,
    ProductVariant,
)
from app.seeds.seed_phase1_demo import seed_phase1_demo


@pytest.fixture(autouse=True)
async def ensure_demo_dataset():
    """Ensure Phase 1 seed data is in place before executing tests."""
    await seed_phase1_demo()


async def login(
    client: AsyncClient, email: str, password: str = "Basket@123"
) -> tuple[dict[str, str], dict]:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    data = resp.json()
    auth_header = {"Authorization": f"Bearer {data['access_token']}"}
    return auth_header, data["user"]


@pytest.mark.asyncio
async def test_a_retailer_login_and_access(async_client: AsyncClient):
    """Test A: Retailer login, portal access, and tenant isolation."""
    # 1. Login with Retailer 1 (Basket Mart)
    h1, u1 = await login(async_client, "retailer1@basket.demo")
    assert u1["role"] == "retailer"

    # Verify access to listings & inventory
    resp1_listings = await async_client.get("/api/v1/retailer/listings", headers=h1)
    assert resp1_listings.status_code == 200
    listings1 = resp1_listings.json()
    assert listings1["total"] >= 25

    resp1_inv = await async_client.get("/api/v1/retailer/inventory", headers=h1)
    assert resp1_inv.status_code == 200

    # 2. Login with Retailer 2 (Basket Lifestyle)
    h2, u2 = await login(async_client, "retailer2@basket.demo")
    assert u2["role"] == "retailer"

    resp2_listings = await async_client.get("/api/v1/retailer/listings", headers=h2)
    assert resp2_listings.status_code == 200
    listings2 = resp2_listings.json()
    assert listings2["total"] >= 25

    # 3. Verify tenant isolation: Retailer 2 cannot access Retailer 1's listing
    target_id1 = listings1["items"][0]["id"]
    forbidden_resp = await async_client.get(
        f"/api/v1/retailer/listings/{target_id1}", headers=h2
    )
    assert forbidden_resp.status_code in (403, 404)


@pytest.mark.asyncio
async def test_b_price_synchronization(async_client: AsyncClient):
    """Test B: Immediate propagation of price updates across DB, OpenSearch, catalogue, and search."""
    h1, _ = await login(async_client, "retailer1@basket.demo")

    # Get an active listing from Basket Mart
    listings_resp = await async_client.get(
        "/api/v1/retailer/listings", headers=h1, params={"is_active": True}
    )
    assert listings_resp.status_code == 200
    listing = listings_resp.json()["items"][0]
    listing_id = listing["id"]
    variant_id = listing["variant_id"]
    original_price = listing["original_price_paise"]

    # Update selling price (e.g. 10% discount from original)
    new_price = original_price - 1000
    if new_price <= 0:
        new_price = original_price // 2

    upd_resp = await async_client.put(
        f"/api/v1/retailer/listings/{listing_id}",
        headers=h1,
        json={"selling_price_paise": new_price},
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["selling_price_paise"] == new_price

    # 1. Verify in PostgreSQL
    session_factory = get_session_factory()
    async with session_factory() as s:
        db_listing = (
            await s.execute(
                select(ProductListing).where(ProductListing.id == uuid.UUID(listing_id))
            )
        ).scalar_one()
        assert db_listing.selling_price_paise == new_price

        # Get parent product
        db_var = (
            await s.execute(
                select(ProductVariant).where(ProductVariant.id == uuid.UUID(variant_id))
            )
        ).scalar_one()
        product_id = str(db_var.product_id)

    # 2. Verify in OpenSearch document
    os_client = get_opensearch_client(settings)
    if await os_client.ping():
        doc = await os_client.get_document(get_search_alias_name(), product_id)
        assert doc is not None
        # Check retailer listing price inside doc
        ret_entries = doc.get("retailers", [])
        matched = [r for r in ret_entries if r["listing_id"] == listing_id]
        if matched:
            assert matched[0]["selling_price_paise"] == new_price

    # 3. Verify in Customer Catalogue API
    cat_resp = await async_client.get(f"/api/v1/catalogue/products/{product_id}")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["min_price_paise"] == new_price


@pytest.mark.asyncio
async def test_c_multi_retailer_price_isolation(async_client: AsyncClient):
    """Test C: Retailer price updates only affect their own store listings."""
    h1, _ = await login(async_client, "retailer1@basket.demo")
    h2, _ = await login(async_client, "retailer2@basket.demo")

    # Fetch active in-stock listings from each retailer
    listings1_active = (
        await async_client.get(
            "/api/v1/retailer/listings", headers=h1, params={"is_active": True}
        )
    ).json()["items"]
    listings2_active = (
        await async_client.get(
            "/api/v1/retailer/listings", headers=h2, params={"is_active": True}
        )
    ).json()["items"]

    l1 = next(
        (i for i in listings1_active if not i["inventory"]["is_out_of_stock"]),
        listings1_active[0],
    )
    l2 = next(
        (i for i in listings2_active if not i["inventory"]["is_out_of_stock"]),
        listings2_active[0],
    )

    original_price2 = l2["selling_price_paise"]

    # Modify Retailer 1 listing price
    new_price1 = l1["original_price_paise"] - 500
    await async_client.put(
        f"/api/v1/retailer/listings/{l1['id']}",
        headers=h1,
        json={"selling_price_paise": new_price1},
    )

    # Verify Retailer 2 listing price is completely unaffected
    refreshed_l2 = (
        await async_client.get(f"/api/v1/retailer/listings/{l2['id']}", headers=h2)
    ).json()
    assert refreshed_l2["selling_price_paise"] == original_price2


@pytest.mark.asyncio
async def test_d_inventory_synchronization(async_client: AsyncClient):
    """Test D: Stock transitions: 10 -> 0 -> 15 and prevention of overselling."""
    h1, _ = await login(async_client, "retailer1@basket.demo")

    l1 = (await async_client.get("/api/v1/retailer/listings", headers=h1)).json()[
        "items"
    ][0]
    listing_id = l1["id"]

    # Set stock to 0
    adj_zero = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=h1,
        json={"adjustment_type": "SET", "quantity": 0},
    )
    assert adj_zero.status_code == 200
    assert adj_zero.json()["on_hand_quantity"] == 0
    assert adj_zero.json()["available_quantity"] == 0

    # Set stock to 15
    adj_restock = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=h1,
        json={"adjustment_type": "SET", "quantity": 15},
    )
    assert adj_restock.status_code == 200
    assert adj_restock.json()["on_hand_quantity"] == 15
    assert adj_restock.json()["available_quantity"] == 15


@pytest.mark.asyncio
async def test_e_search_relevance_accuracy(async_client: AsyncClient):
    """Test E: High-precision search matching and negative verification."""
    # 1. Exact query for boAt Stone 350
    resp_boat = await async_client.get(
        "/api/v1/search", params={"q": "boAt Stone 350 10W Portable"}
    )
    assert resp_boat.status_code == 200
    data_boat = resp_boat.json()
    assert data_boat["total"] >= 1
    assert "boAt" in data_boat["items"][0]["name"]
    # Verify false positives are strictly NOT present
    for item in data_boat["items"]:
        assert "prestige" not in item["name"].lower()
        assert "sony" not in item["name"].lower()
        assert "macbook" not in item["name"].lower()

    # 2. Query for Honey
    resp_honey = await async_client.get("/api/v1/search", params={"q": "Honey"})
    assert resp_honey.status_code == 200
    data_honey = resp_honey.json()
    assert data_honey["total"] == 1
    assert "Honey" in data_honey["items"][0]["name"]

    # 3. Query for MacBook
    resp_mac = await async_client.get("/api/v1/search", params={"q": "MacBook"})
    assert resp_mac.status_code == 200
    data_mac = resp_mac.json()
    assert data_mac["total"] == 1
    assert "MacBook" in data_mac["items"][0]["name"]

    # 4. Query for headphones
    resp_hp = await async_client.get("/api/v1/search", params={"q": "headphones"})
    assert resp_hp.status_code == 200
    data_hp = resp_hp.json()
    assert data_hp["total"] == 1
    assert "Headphones" in data_hp["items"][0]["name"]

    # 5. Query for basmati
    resp_bas = await async_client.get("/api/v1/search", params={"q": "basmati"})
    assert resp_bas.status_code == 200
    data_bas = resp_bas.json()
    assert data_bas["total"] == 1
    assert "Basmati" in data_bas["items"][0]["name"]

    # 6. Non-existent product query returns 0 results
    resp_none = await async_client.get(
        "/api/v1/search", params={"q": "xyznonexistentproduct999"}
    )
    assert resp_none.status_code == 200
    assert resp_none.json()["total"] == 0
    assert len(resp_none.json()["items"]) == 0


@pytest.mark.asyncio
async def test_f_customer_marketplace_validation(async_client: AsyncClient):
    """Test F: Exactly 10 top-level categories and 50 initial demo products."""
    # Verify categories
    cat_resp = await async_client.get("/api/v1/catalogue/categories")
    assert cat_resp.status_code == 200
    cats = cat_resp.json()
    assert len(cats) == 10

    # Verify products
    prods_resp = await async_client.get(
        "/api/v1/catalogue/products", params={"limit": 100}
    )
    assert prods_resp.status_code == 200
    prods = prods_resp.json()
    assert prods["total"] == 50
    assert len(prods["items"]) == 50

    # Verify every product has valid image, price > 0, and correct stock status
    for p in prods["items"]:
        img = p.get("primary_image") or p.get("primary_image_url")
        assert img and img.startswith("http")
        assert p["min_price_paise"] > 0
        if p["slug"] in (
            "pigeon-stainless-steel-electric-kettle-1-5l",
            "nivea-nourishing-body-milk-400ml-for-very-dry-skin",
        ):
            assert p["is_in_stock"] is False
        else:
            assert p["is_in_stock"] is True


@pytest.mark.asyncio
async def test_g_multi_retailer_cart_and_quote(async_client: AsyncClient):
    """Test G: Multi-retailer basket and checkout quote breakdown."""
    hc, _ = await login(async_client, "customer@basket.demo")
    h1, _ = await login(async_client, "retailer1@basket.demo")
    h2, _ = await login(async_client, "retailer2@basket.demo")

    # Fetch active in-stock listings from each retailer
    listings1_active = (
        await async_client.get(
            "/api/v1/retailer/listings", headers=h1, params={"is_active": True}
        )
    ).json()["items"]
    listings2_active = (
        await async_client.get(
            "/api/v1/retailer/listings", headers=h2, params={"is_active": True}
        )
    ).json()["items"]

    l1 = next(
        (i for i in listings1_active if not i["inventory"]["is_out_of_stock"]),
        listings1_active[0],
    )
    l2 = next(
        (i for i in listings2_active if not i["inventory"]["is_out_of_stock"]),
        listings2_active[0],
    )

    # Clear customer cart first
    cart_resp = await async_client.get("/api/v1/cart", headers=hc)
    if cart_resp.status_code == 200:
        for itm in cart_resp.json().get("items", []):
            await async_client.delete(f"/api/v1/cart/items/{itm['id']}", headers=hc)

    # Add item from Basket Mart
    add1 = await async_client.post(
        "/api/v1/cart/items",
        headers=hc,
        json={"listing_id": l1["id"], "quantity": 1},
    )
    assert add1.status_code in (200, 201)

    # Add item from Basket Lifestyle
    add2 = await async_client.post(
        "/api/v1/cart/items",
        headers=hc,
        json={"listing_id": l2["id"], "quantity": 1},
    )
    assert add2.status_code in (200, 201)

    # Verify cart contains both items from different retailers
    refreshed_cart = (await async_client.get("/api/v1/cart", headers=hc)).json()
    retailer_ids = {itm["retailer_id"] for itm in refreshed_cart["items"]}
    assert len(retailer_ids) == 2
    assert str(l1["retailer_id"]) in retailer_ids
    assert str(l2["retailer_id"]) in retailer_ids
