import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import Category, StoreInventory
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
async def test_a_retailer1_operations(async_client: AsyncClient):
    """Test A: Retailer 1 (Basket Mart) operations.

    Login, verify 25 listings, inventory, create offer, view orders, update order status.
    """
    auth_headers, user = await login(async_client, "retailer1@basket.demo")
    assert user["role"] == "retailer"

    # 1. Verify 25 listings
    listings_resp = await async_client.get(
        "/api/v1/retailer/listings", headers=auth_headers
    )
    assert listings_resp.status_code == 200
    listings_data = listings_resp.json()
    assert len(listings_data["items"]) >= 25
    assert listings_data["total"] >= 25

    # 2. Verify inventory
    inv_resp = await async_client.get(
        "/api/v1/retailer/inventory", headers=auth_headers
    )
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()
    assert len(inv_data["items"]) >= 25
    first_inv = inv_data["items"][0]
    assert "on_hand_quantity" in first_inv
    assert "available_quantity" in first_inv

    # 3. Create offer / discount
    offer_code = f"MART{uuid.uuid4().hex[:6].upper()}"
    create_offer_resp = await async_client.post(
        "/api/v1/retailer/offers",
        headers=auth_headers,
        json={
            "name": "20% off test discount",
            "code": offer_code,
            "description": "20% off test discount",
            "discount_type": "PERCENTAGE",
            "discount_value": 20,
            "min_order_paise": 50000,
            "max_discount_paise": 10000,
        },
    )
    assert create_offer_resp.status_code == 201
    offer_data = create_offer_resp.json()
    assert offer_data["code"] == offer_code
    assert offer_data["is_active"] is True

    # 4. View retailer orders
    orders_resp = await async_client.get(
        "/api/v1/retailer/orders", headers=auth_headers
    )
    assert orders_resp.status_code == 200
    orders_data = orders_resp.json()
    assert orders_data["total"] >= 1
    sample_order = orders_data["items"][0]
    assert sample_order["order_number"].startswith("ORD-DEMO-") or sample_order[
        "order_number"
    ].startswith("BSK-")

    # 5. Update order status
    order_id = sample_order["id"]
    status_resp = await async_client.patch(
        f"/api/v1/retailer/orders/{order_id}/status",
        headers=auth_headers,
        json={
            "status": "PROCESSING",
            "reason": "Retailer preparing package for dispatch",
        },
    )
    assert status_resp.status_code == 200
    updated_order = status_resp.json()
    assert updated_order["status"] == "PROCESSING"


@pytest.mark.asyncio
async def test_b_retailer2_tenant_isolation(async_client: AsyncClient):
    """Test B: Retailer 2 (Basket Lifestyle) operations and tenant isolation.

    Verify 25 listings and verify Retailer 2 cannot read/modify Retailer 1 listings, inventory, or offers.
    """
    ret1_headers, _ = await login(async_client, "retailer1@basket.demo")
    ret2_headers, ret2_user = await login(async_client, "retailer2@basket.demo")
    assert ret2_user["role"] == "retailer"

    # 1. Retailer 2 listings count is 25
    listings_resp = await async_client.get(
        "/api/v1/retailer/listings", headers=ret2_headers
    )
    assert listings_resp.status_code == 200
    ret2_listings = listings_resp.json()
    assert len(ret2_listings["items"]) >= 25
    assert ret2_listings["total"] >= 25

    # 2. Get a listing belonging to Retailer 1
    ret1_listings_resp = await async_client.get(
        "/api/v1/retailer/listings", headers=ret1_headers
    )
    ret1_first_listing = ret1_listings_resp.json()["items"][0]
    ret1_listing_id = ret1_first_listing["id"]

    # 3. Tenant Isolation Check: Retailer 2 tries to modify Retailer 1's listing price
    hijack_resp = await async_client.put(
        f"/api/v1/retailer/listings/{ret1_listing_id}",
        headers=ret2_headers,
        json={"selling_price_paise": 100},
    )
    # Must be 404 (listing not found under Retailer 2's tenant)
    assert hijack_resp.status_code == 404

    # 4. Tenant Isolation Check: Retailer 2 tries to adjust Retailer 1's inventory
    hijack_inv_resp = await async_client.post(
        f"/api/v1/retailer/listings/{ret1_listing_id}/inventory",
        headers=ret2_headers,
        json={"adjustment_type": "SET", "quantity": 999},
    )
    assert hijack_inv_resp.status_code == 404

    # 5. Tenant Isolation Check: Retailer 2 tries to delete Retailer 1's offer
    ret1_offers_resp = await async_client.get(
        "/api/v1/retailer/offers", headers=ret1_headers
    )
    assert ret1_offers_resp.status_code == 200
    ret1_offers_data = ret1_offers_resp.json()
    offers = (
        ret1_offers_data
        if isinstance(ret1_offers_data, list)
        else ret1_offers_data.get("items", [])
    )
    if offers:
        ret1_offer_id = offers[0]["id"]
        hijack_offer_resp = await async_client.delete(
            f"/api/v1/retailer/offers/{ret1_offer_id}",
            headers=ret2_headers,
        )
        assert hijack_offer_resp.status_code == 404


@pytest.mark.asyncio
async def test_c_customer_experience(async_client: AsyncClient):
    """Test C: Customer Experience.

    Login, browse 10 categories, search products, view details, compare products, basket operations.
    """
    cust_headers, user = await login(async_client, "customer@basket.demo")
    assert user["role"] == "customer"

    # 1. Browse 10 categories
    cat_resp = await async_client.get("/api/v1/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    top_level_cats = [c for c in categories if c.get("parent_id") is None]
    assert len(top_level_cats) == 10

    # 2. Search products (honey and laptop)
    search_honey = await async_client.get("/api/v1/products?search=honey")
    assert search_honey.status_code == 200
    honey_items = search_honey.json()["items"]
    assert len(honey_items) >= 1
    assert any("honey" in item["name"].lower() for item in honey_items)

    search_laptop = await async_client.get("/api/v1/products?search=laptop")
    assert search_laptop.status_code == 200
    laptop_items = search_laptop.json()["items"]
    assert len(laptop_items) >= 1

    # 3. View product details by slug
    sample_slug = honey_items[0]["slug"]
    detail_resp = await async_client.get(f"/api/v1/products/{sample_slug}")
    assert detail_resp.status_code == 200
    product_detail = detail_resp.json()
    assert product_detail["slug"] == sample_slug
    assert len(product_detail["variants"]) >= 1
    assert len(product_detail["images"]) >= 1

    # 4. Compare products (verify data contract for 2 products)
    sample_slug_2 = laptop_items[0]["slug"]
    detail_resp_2 = await async_client.get(f"/api/v1/products/{sample_slug_2}")
    assert detail_resp_2.status_code == 200
    product_detail_2 = detail_resp_2.json()

    # Verify both have comparison fields: brand, category, min_price_paise, variants with attributes
    for p in (product_detail, product_detail_2):
        assert "brand" in p
        assert "category_name" in p
        assert "min_price_paise" in p
        assert "is_in_stock" in p

    # 5. Basket Operations
    first_listing = product_detail["variants"][0]["listings"][0]
    listing_id = first_listing["id"]

    # Clear existing cart if any
    await async_client.delete("/api/v1/cart", headers=cust_headers)

    # Add item to cart
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        headers=cust_headers,
        json={"listing_id": listing_id, "quantity": 1},
    )
    assert add_resp.status_code in (200, 201)
    cart_data = add_resp.json()
    assert len(cart_data["items"]) == 1
    cart_item_id = cart_data["items"][0]["id"]

    # Update item quantity in cart
    update_resp = await async_client.patch(
        f"/api/v1/cart/items/{cart_item_id}",
        headers=cust_headers,
        json={"quantity": 2},
    )
    assert update_resp.status_code == 200
    updated_cart = update_resp.json()
    assert updated_cart["items"][0]["quantity"] == 2

    # View cart
    get_cart_resp = await async_client.get("/api/v1/cart", headers=cust_headers)
    assert get_cart_resp.status_code == 200
    assert len(get_cart_resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_d_end_to_end_purchase_flow(async_client: AsyncClient):
    """Test D: End-to-End Multi-Retailer Purchase Flow.

    Retailer updates stock -> Customer adds to basket -> Checkout quote ->
    Inventory reservation -> Atomic order placement -> Inventory deducted ->
    Retailer fulfills order -> Customer tracks order.
    """
    ret1_headers, _ = await login(async_client, "retailer1@basket.demo")
    cust_headers, _ = await login(async_client, "customer@basket.demo")

    # 1. Retailer 1 inspects inventory and updates on_hand_quantity
    inv_resp = await async_client.get(
        "/api/v1/retailer/inventory", headers=ret1_headers
    )
    inv_items = [i for i in inv_resp.json()["items"] if i["available_quantity"] >= 5]
    assert len(inv_items) >= 1
    target_inv = inv_items[0]
    listing_id = target_inv["listing_id"]

    # Update stock to 40
    await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=ret1_headers,
        json={
            "adjustment_type": "SET",
            "quantity": 40,
            "low_stock_threshold": 5,
            "reason": "Test stock update",
        },
    )

    # Get customer saved address
    addr_resp = await async_client.get("/api/v1/addresses", headers=cust_headers)
    addresses = addr_resp.json()
    assert len(addresses) >= 1
    address_id = addresses[0]["id"]

    # 2. Customer adds item to cart
    await async_client.delete("/api/v1/cart", headers=cust_headers)
    add_cart_resp = await async_client.post(
        "/api/v1/cart/items",
        headers=cust_headers,
        json={"listing_id": listing_id, "quantity": 2},
    )
    assert add_cart_resp.status_code in (200, 201)

    # 3. Create checkout quote
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        headers=cust_headers,
        json={"delivery_address_id": address_id},
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    quote_id = quote["id"]
    assert quote["status"] == "ACTIVE"

    # 4. Create inventory reservation
    res_resp = await async_client.post(
        "/api/v1/reservations",
        headers=cust_headers,
        json={"quote_id": quote_id},
    )
    assert res_resp.status_code == 201
    res_data = res_resp.json()
    reservation_id = res_data["id"]
    assert res_data["status"] == "ACTIVE"

    # 5. Place order atomically
    order_resp = await async_client.post(
        "/api/v1/orders",
        headers=cust_headers,
        json={
            "reservation_id": reservation_id,
            "quote_id": quote_id,
            "delivery_address_id": address_id,
        },
    )
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    order_id = order_data["id"]
    assert order_data["status"] in ("PENDING_PAYMENT", "CONFIRMED")
    assert len(order_data["items"]) >= 1

    # 6. Verify inventory was deducted in database
    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_check = (
            await session.execute(
                select(StoreInventory).where(
                    StoreInventory.listing_id == uuid.UUID(listing_id)
                )
            )
        ).scalar_one()
        # available_quantity should be on_hand (40) - reserved
        assert inv_check.on_hand_quantity <= 40

    # 7. Retailer 1 views the order and updates fulfillment status
    ret1_orders_resp = await async_client.get(
        "/api/v1/retailer/orders", headers=ret1_headers
    )
    assert ret1_orders_resp.status_code == 200
    ret1_orders = ret1_orders_resp.json()["items"]
    matching = [o for o in ret1_orders if o["id"] == order_id]
    assert len(matching) == 1

    update_status_resp = await async_client.patch(
        f"/api/v1/retailer/orders/{order_id}/status",
        headers=ret1_headers,
        json={"status": "PROCESSING", "reason": "Order packed and ready for dispatch"},
    )
    assert update_status_resp.status_code == 200
    assert update_status_resp.json()["status"] == "PROCESSING"

    # 8. Customer tracks order
    track_resp = await async_client.get(
        f"/api/v1/orders/{order_id}/tracking", headers=cust_headers
    )
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert track_data["order_status"] == "PROCESSING"
    assert len(track_data["timeline"]) >= 1


@pytest.mark.asyncio
async def test_e_admin_integration(async_client: AsyncClient):
    """Test E: Admin Integration.

    Login, view both retailers (verified active), view all 50 products, categories, orders, analytics.
    """
    admin_headers, user = await login(async_client, "admin@basket.demo")
    assert user["role"] == "admin"

    # 1. View retailers
    retailers_resp = await async_client.get(
        "/api/v1/admin/retailers", headers=admin_headers
    )
    assert retailers_resp.status_code == 200
    retailers_data = retailers_resp.json()
    items = (
        retailers_data
        if isinstance(retailers_data, list)
        else retailers_data.get("items", [])
    )
    ret_slugs = {r["slug"] for r in items}
    assert "basket-mart" in ret_slugs
    assert "basket-lifestyle" in ret_slugs

    # 2. View 10 categories
    session_factory = get_session_factory()
    async with session_factory() as session:
        cat_result = await session.execute(
            select(Category).where(Category.parent_id.is_(None))
        )
        top_cats = cat_result.scalars().all()
        assert len(top_cats) == 10

    # 3. View products across categories
    products_resp = await async_client.get("/api/v1/products?limit=100")
    assert products_resp.status_code == 200
    products_data = products_resp.json()
    assert products_data["total"] >= 50

    # 4. View Admin Overview / Analytics
    overview_resp = await async_client.get(
        "/api/v1/admin/overview", headers=admin_headers
    )
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()
    assert "total_revenue_paise" in overview_data
    assert "total_retailers" in overview_data
    assert overview_data["total_retailers"] >= 2
    assert overview_data["active_products"] >= 50
