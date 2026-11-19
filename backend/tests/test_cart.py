import uuid

import pytest
from httpx import AsyncClient

from tests.factories import get_test_listings


@pytest.mark.asyncio
async def test_guest_cart_lifecycle(async_client: AsyncClient):
    # 1. Fresh guest GET cart should return active empty cart and set cookie
    response = await async_client.get("/api/v1/cart")
    assert response.status_code == 200
    cart = response.json()
    assert cart["status"] == "ACTIVE"
    assert cart["items"] == []
    assert cart["item_count"] == 0
    assert cart["total_quantity"] == 0
    assert cart["subtotal_paise"] == 0
    assert "basket_guest_cart" in response.cookies

    # 2. Add an item using the guest cookie
    listings = await get_test_listings(async_client)
    assert len(listings) >= 1
    listing = listings[0]

    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 2},
    )
    assert add_resp.status_code == 200
    added_cart = add_resp.json()
    assert added_cart["item_count"] == 1
    assert added_cart["total_quantity"] == 2
    assert added_cart["items"][0]["quantity"] == 2
    assert added_cart["items"][0]["unit_price_paise"] == listing["selling_price_paise"]
    assert (
        added_cart["items"][0]["subtotal_paise"] == listing["selling_price_paise"] * 2
    )
    assert added_cart["subtotal_paise"] == listing["selling_price_paise"] * 2

    # 3. Fetch cart again with guest cookie
    get_resp = await async_client.get("/api/v1/cart")
    assert get_resp.status_code == 200
    fetched_cart = get_resp.json()
    assert fetched_cart["item_count"] == 1
    assert fetched_cart["total_quantity"] == 2
    item_id = fetched_cart["items"][0]["id"]

    # 4. Update item quantity
    update_resp = await async_client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 4},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["total_quantity"] == 4
    assert update_resp.json()["items"][0]["quantity"] == 4

    # 5. Remove item
    remove_resp = await async_client.delete(
        f"/api/v1/cart/items/{item_id}",
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["item_count"] == 0
    assert remove_resp.json()["total_quantity"] == 0


@pytest.mark.asyncio
async def test_add_existing_item_increments_quantity(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    assert len(listings) >= 1
    listing = listings[0]

    # Add item 1 unit
    r1 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert r1.status_code == 200
    assert "basket_guest_cart" in r1.cookies
    assert r1.json()["total_quantity"] == 1

    # Add same listing 2 more units
    r2 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 2},
    )
    assert r2.status_code == 200
    assert r2.json()["item_count"] == 1
    assert r2.json()["total_quantity"] == 3
    assert r2.json()["items"][0]["quantity"] == 3


@pytest.mark.asyncio
async def test_multi_retailer_cart_breakdown(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    # Find two listings from different retailers
    retailer_listings = {}
    for item in listings:
        r_id = item["retailer_id"]
        if r_id not in retailer_listings:
            retailer_listings[r_id] = item
        if len(retailer_listings) >= 2:
            break

    if len(retailer_listings) >= 2:
        list_items = list(retailer_listings.values())
        l1, l2 = list_items[0], list_items[1]

        r1 = await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": l1["id"], "quantity": 1},
        )
        assert r1.status_code == 200
        assert "basket_guest_cart" in r1.cookies

        r2 = await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": l2["id"], "quantity": 2},
        )
        assert r2.status_code == 200
        cart = r2.json()
        assert cart["item_count"] == 2
        assert cart["total_quantity"] == 3
        assert len(cart["retailers"]) == 2


@pytest.mark.asyncio
async def test_clear_cart(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    assert len(listings) >= 1
    listing = listings[0]

    r1 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert r1.status_code == 200
    assert "basket_guest_cart" in r1.cookies
    assert r1.json()["item_count"] == 1

    clear_resp = await async_client.delete(
        "/api/v1/cart",
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["item_count"] == 0
    assert clear_resp.json()["items"] == []


@pytest.mark.asyncio
async def test_quantity_limits_and_validation(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    assert len(listings) >= 1
    listing = listings[0]

    # Quantity 0 -> 422
    r_zero = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 0},
    )
    assert r_zero.status_code == 422

    # Quantity 11 -> 422
    r_eleven = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 11},
    )
    assert r_eleven.status_code == 422

    # Add 8
    r_valid = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 8},
    )
    assert r_valid.status_code == 200
    assert "basket_guest_cart" in r_valid.cookies

    # Try adding 3 more (total 11 > 10) -> 400
    r_over = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 3},
    )
    assert r_over.status_code == 400
    assert r_over.json()["error"]["code"] == "MAX_QUANTITY_EXCEEDED"


@pytest.mark.asyncio
async def test_guest_to_authenticated_cart_migration(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    assert len(listings) >= 2
    l1, l2 = listings[0], listings[1]

    # 1. Create guest cart with l1 (qty 2) and l2 (qty 1)
    g1 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": l1["id"], "quantity": 2},
    )
    assert g1.status_code == 200
    guest_token = g1.cookies["basket_guest_cart"]

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": l2["id"], "quantity": 1},
    )

    # 2. Register new customer
    email = f"cart_test_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Cart Tester",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    auth_header = {"Authorization": f"Bearer {auth_data['access_token']}"}

    # 3. Customer has l1 (qty 3) in their cart already
    u1 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": l1["id"], "quantity": 3},
        headers=auth_header,
    )
    assert u1.status_code == 200
    assert u1.json()["total_quantity"] == 3

    # 4. Merge guest cart into customer cart
    merge_resp = await async_client.post(
        "/api/v1/cart/merge",
        json={"guest_token": guest_token},
        headers=auth_header,
    )
    assert merge_resp.status_code == 200
    merge_data = merge_resp.json()
    merged_cart = merge_data["cart"]

    # l1 combined: 3 + 2 = 5
    # l2 added: 1
    # total items = 2, total_quantity = 6
    assert merged_cart["item_count"] == 2
    assert merged_cart["total_quantity"] == 6

    # 5. Clear cookies on client (simulate guest with old guest token after logout)
    async_client.cookies.clear()
    async_client.cookies.set(
        "basket_guest_cart", guest_token, domain="testserver.local"
    )

    # Verify guest cart with old token:
    # Since the old guest cart is MERGED, a new empty guest cart is created
    guest_check = await async_client.get("/api/v1/cart")
    assert guest_check.status_code == 200
    assert guest_check.json()["item_count"] == 0
    assert guest_check.json()["total_quantity"] == 0


@pytest.mark.asyncio
async def test_cart_item_not_found(async_client: AsyncClient):
    fake_item_id = uuid.uuid4()
    resp = await async_client.delete(f"/api/v1/cart/items/{fake_item_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_cart_nonexistent_listing(async_client: AsyncClient):
    fake_listing_id = uuid.uuid4()
    resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(fake_listing_id), "quantity": 1},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "ITEM_UNAVAILABLE"


@pytest.mark.asyncio
async def test_cart_isolation_between_customers(async_client: AsyncClient):
    listings = await get_test_listings(async_client)
    assert len(listings) >= 1
    listing = listings[0]

    # Customer 1
    c1_email = f"c1_{uuid.uuid4().hex[:8]}@example.com"
    r1 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": c1_email,
            "password": "Password123!",
            "full_name": "Customer One",
            "phone": "+919876543211",
        },
    )
    assert r1.status_code == 201
    c1_token = r1.json()["access_token"]
    c1_header = {"Authorization": f"Bearer {c1_token}"}

    # C1 adds item
    c1_add = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 2},
        headers=c1_header,
    )
    assert c1_add.status_code == 200
    assert c1_add.json()["total_quantity"] == 2
    c1_item_id = c1_add.json()["items"][0]["id"]

    # Customer 2
    c2_email = f"c2_{uuid.uuid4().hex[:8]}@example.com"
    r2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": c2_email,
            "password": "Password123!",
            "full_name": "Customer Two",
            "phone": "+919876543212",
        },
    )
    assert r2.status_code == 201
    c2_token = r2.json()["access_token"]
    c2_header = {"Authorization": f"Bearer {c2_token}"}

    # C2 gets cart -> empty
    c2_cart = await async_client.get("/api/v1/cart", headers=c2_header)
    assert c2_cart.status_code == 200
    assert c2_cart.json()["item_count"] == 0

    # C2 tries to delete C1's cart item -> 404
    c2_delete = await async_client.delete(
        f"/api/v1/cart/items/{c1_item_id}",
        headers=c2_header,
    )
    assert c2_delete.status_code == 404
    assert c2_delete.json()["error"]["code"] == "ITEM_NOT_FOUND"
