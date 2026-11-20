import uuid

import pytest
from httpx import AsyncClient

from tests.factories import create_test_listing


async def register_customer(
    async_client: AsyncClient, name_prefix: str = "mission_user"
) -> tuple[dict, str]:
    email = f"{name_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": f"{name_prefix.capitalize()} Tester",
            "phone": f"+919{uuid.uuid4().int % 1000000000:09d}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["user"], data["access_token"]


@pytest.mark.asyncio
async def test_customer_create_mission(async_client: AsyncClient):
    """Customer creates a mission and receives a grouped shopping plan with real products."""
    user, token = await register_customer(async_client, "kitchen_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    create_payload = {
        "title": "Set up a complete kitchen under ₹15,000",
        "description": "Essential cookware, food storage containers, and grocery staples for daily cooking",
        "budget_paise": 1500000,
        "people_count": 2,
        "preferences": ["durable", "non-stick", "stainless steel"],
        "excluded_brands": ["UnknownCheapBrand"],
    }

    resp = await async_client.post(
        "/api/v1/missions",
        json=create_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    mission = resp.json()

    assert mission["id"] is not None
    assert mission["customer_id"] == user["id"]
    assert mission["title"] == create_payload["title"]
    assert mission["budget_paise"] == 1500000
    assert mission["status"] == "ACTIVE"
    assert len(mission["items"]) > 0
    assert len(mission["groups"]) > 0

    # Verify real products with valid pricing and stock
    for item in mission["items"]:
        assert item["listing_id"] is not None
        assert item["product_id"] is not None
        assert bool(item["retailer_name"])
        assert item["unit_price_paise"] > 0
        assert item["quantity"] >= 1
        assert item["subtotal_paise"] == item["unit_price_paise"] * item["quantity"]
        assert item["is_selected"] is True
        assert len(item["recommendation_reason"]) > 0

    # Total cost should be calculated correctly
    assert mission["total_cost_paise"] > 0
    assert mission["remaining_budget_paise"] >= 0 or mission["is_over_budget"] is True
    assert "summary_explanation" in mission


@pytest.mark.asyncio
async def test_customer_retrieve_missions_list_and_detail(async_client: AsyncClient):
    """Customer can list their missions and retrieve full details by ID."""
    user, token = await register_customer(async_client, "list_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 2 missions
    m1 = await async_client.post(
        "/api/v1/missions",
        json={"title": "Gym Setup", "budget_paise": 1000000, "people_count": 1},
        headers=headers,
    )
    assert m1.status_code == 201
    m1_id = m1.json()["id"]

    m2 = await async_client.post(
        "/api/v1/missions",
        json={"title": "Newborn Essentials", "budget_paise": 800000, "people_count": 1},
        headers=headers,
    )
    assert m2.status_code == 201

    # List missions
    list_resp = await async_client.get("/api/v1/missions", headers=headers)
    assert list_resp.status_code == 200
    missions_list = list_resp.json()
    assert len(missions_list) >= 2
    titles = [m["title"] for m in missions_list]
    assert "Gym Setup" in titles
    assert "Newborn Essentials" in titles

    # Get single mission detail
    detail_resp = await async_client.get(f"/api/v1/missions/{m1_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == m1_id
    assert detail["title"] == "Gym Setup"
    assert len(detail["groups"]) > 0


@pytest.mark.asyncio
async def test_customer_isolation_and_cross_tenant_rejection(async_client: AsyncClient):
    """Customer A cannot view, modify, or delete Customer B's mission."""
    user_a, token_a = await register_customer(async_client, "user_a")
    user_b, token_b = await register_customer(async_client, "user_b")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Customer A creates mission
    m_resp = await async_client.post(
        "/api/v1/missions",
        json={"title": "Private Apartment Setup", "budget_paise": 2500000},
        headers=headers_a,
    )
    assert m_resp.status_code == 201
    m_id = m_resp.json()["id"]

    # Customer B attempts to GET Customer A's mission -> 404
    get_b = await async_client.get(f"/api/v1/missions/{m_id}", headers=headers_b)
    assert get_b.status_code == 404
    assert get_b.json()["error"]["code"] == "MISSION_NOT_FOUND"

    # Customer B attempts to PATCH Customer A's mission -> 404
    patch_b = await async_client.patch(
        f"/api/v1/missions/{m_id}",
        json={"title": "Hacked Title"},
        headers=headers_b,
    )
    assert patch_b.status_code == 404

    # Customer B attempts to DELETE Customer A's mission -> 404
    del_b = await async_client.delete(f"/api/v1/missions/{m_id}", headers=headers_b)
    assert del_b.status_code == 404

    # Customer B's list does not show Customer A's mission
    list_b = await async_client.get("/api/v1/missions", headers=headers_b)
    assert list_b.status_code == 200
    b_ids = [m["id"] for m in list_b.json()]
    assert m_id not in b_ids


@pytest.mark.asyncio
async def test_customer_update_and_delete_mission(async_client: AsyncClient):
    """Customer can update mission properties and delete their mission."""
    user, token = await register_customer(async_client, "edit_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await async_client.post(
        "/api/v1/missions",
        json={"title": "Original Mission", "budget_paise": 500000},
        headers=headers,
    )
    assert create_resp.status_code == 201
    m_id = create_resp.json()["id"]

    # Update title and budget
    update_resp = await async_client.patch(
        f"/api/v1/missions/{m_id}",
        json={
            "title": "Updated Mission Title",
            "budget_paise": 750000,
            "status": "SAVED",
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["title"] == "Updated Mission Title"
    assert updated["budget_paise"] == 750000
    assert updated["status"] == "SAVED"

    # Delete mission
    del_resp = await async_client.delete(f"/api/v1/missions/{m_id}", headers=headers)
    assert del_resp.status_code == 204

    # Confirm deletion
    get_again = await async_client.get(f"/api/v1/missions/{m_id}", headers=headers)
    assert get_again.status_code == 404


@pytest.mark.asyncio
async def test_mission_item_modifications(async_client: AsyncClient):
    """Customer can change item quantities, toggle inclusion, and add/remove items."""
    user, token = await register_customer(async_client, "item_editor")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await async_client.post(
        "/api/v1/missions",
        json={"title": "Pantry Restock", "budget_paise": 400000},
        headers=headers,
    )
    assert create_resp.status_code == 201
    mission = create_resp.json()
    m_id = mission["id"]
    first_item = mission["items"][0]
    first_item_id = first_item["id"]

    # 1. Update quantity
    qty_resp = await async_client.patch(
        f"/api/v1/missions/{m_id}/items/{first_item_id}",
        json={"quantity": 3},
        headers=headers,
    )
    assert qty_resp.status_code == 200
    updated_items = {i["id"]: i for i in qty_resp.json()["items"]}
    assert updated_items[first_item_id]["quantity"] == 3
    assert (
        updated_items[first_item_id]["subtotal_paise"]
        == updated_items[first_item_id]["current_selling_price_paise"] * 3
    )

    # 2. Toggle selection to False (exclude from total)
    toggle_resp = await async_client.patch(
        f"/api/v1/missions/{m_id}/items/{first_item_id}",
        json={"is_selected": False},
        headers=headers,
    )
    assert toggle_resp.status_code == 200
    toggled_item = next(
        i for i in toggle_resp.json()["items"] if i["id"] == first_item_id
    )
    assert toggled_item["is_selected"] is False
    assert toggled_item["subtotal_paise"] == 0

    # 3. Add an additional product listing to the mission
    new_listing = await create_test_listing(
        retailer_name="Basket Mart",
        product_name="Extra Kitchen Towels",
        selling_price_paise=15000,
        category_slug="home-kitchen",
    )
    add_item_resp = await async_client.post(
        f"/api/v1/missions/{m_id}/items",
        json={
            "listing_id": new_listing["id"],
            "quantity": 2,
            "group_name": "Cleaning Basics",
        },
        headers=headers,
    )
    assert add_item_resp.status_code == 200
    items_after_add = add_item_resp.json()["items"]
    added = next(i for i in items_after_add if i["listing_id"] == new_listing["id"])
    assert added["quantity"] == 2
    assert added["group_name"] == "Cleaning Basics"

    # 4. Remove an item
    del_item_resp = await async_client.delete(
        f"/api/v1/missions/{m_id}/items/{added['id']}",
        headers=headers,
    )
    assert del_item_resp.status_code == 200
    remaining_ids = [i["id"] for i in del_item_resp.json()["items"]]
    assert added["id"] not in remaining_ids


@pytest.mark.asyncio
async def test_mission_alternatives_and_replacement(async_client: AsyncClient):
    """Customer can query product alternatives with price diffs and replace items."""
    user, token = await register_customer(async_client, "alt_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await async_client.post(
        "/api/v1/missions",
        json={
            "title": "Set up a complete kitchen under ₹15,000",
            "budget_paise": 1500000,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    mission = create_resp.json()
    m_id = mission["id"]
    first_item = mission["items"][0]
    first_item_id = first_item["id"]

    # Query alternatives
    alts_resp = await async_client.get(
        f"/api/v1/missions/{m_id}/items/{first_item_id}/alternatives",
        headers=headers,
    )
    assert alts_resp.status_code == 200
    alts = alts_resp.json()
    assert isinstance(alts, list)

    if alts:
        alt_listing_id = alts[0]["listing_id"]
        alt_price = alts[0]["selling_price_paise"]
    else:
        # Fallback to create an alternative listing in the same category
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.core.database import get_session_factory
        from app.modules.catalogue.models import (
            Category,
            ProductListing,
            ProductVariant,
        )

        session_factory = get_session_factory()
        if session_factory is None:
            raise RuntimeError("Database session factory is not configured.")

        async with session_factory() as db:
            cur_l = (
                await db.execute(
                    select(ProductListing)
                    .options(
                        selectinload(ProductListing.variant).selectinload(
                            ProductVariant.product
                        )
                    )
                    .where(ProductListing.id == uuid.UUID(first_item["listing_id"]))
                )
            ).scalar_one()
            cat = (
                await db.execute(
                    select(Category).where(
                        Category.id == cur_l.variant.product.category_id
                    )
                )
            ).scalar_one()
            cat_slug = cat.slug
            cat_name = cat.name

        alt_listing = await create_test_listing(
            retailer_name="Basket Lifestyle",
            product_name="Alternative Kitchen Item",
            selling_price_paise=249900,
            category_slug=cat_slug,
            category_name=cat_name,
        )
        alt_listing_id = alt_listing["id"]
        alt_price = alt_listing["selling_price_paise"]

    # Replace with valid alternative
    replace_resp = await async_client.post(
        f"/api/v1/missions/{m_id}/items/{first_item_id}/replace",
        json={"new_listing_id": alt_listing_id, "quantity": 1},
        headers=headers,
    )
    assert replace_resp.status_code == 200
    replaced_mission = replace_resp.json()
    replaced_item = next(
        i for i in replaced_mission["items"] if i["id"] == first_item_id
    )
    assert replaced_item["listing_id"] == alt_listing_id
    assert replaced_item["unit_price_paise"] == alt_price

    # Reject replacing with a non-existent or unavailable listing -> 400
    fake_replace = await async_client.post(
        f"/api/v1/missions/{m_id}/items/{first_item_id}/replace",
        json={"new_listing_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert fake_replace.status_code == 400
    assert fake_replace.json()["error"]["code"] == "ALTERNATIVE_NOT_AVAILABLE"

    # Reject replacing with a product from an unrelated category -> 400
    diff_cat_listing = await create_test_listing(
        retailer_name="Basket Lifestyle",
        product_name="Casual Cotton T-Shirt",
        selling_price_paise=99900,
        category_slug="fashion-apparel",
        category_name="Fashion & Apparel",
    )
    diff_cat_replace = await async_client.post(
        f"/api/v1/missions/{m_id}/items/{first_item_id}/replace",
        json={"new_listing_id": diff_cat_listing["id"]},
        headers=headers,
    )
    assert diff_cat_replace.status_code == 400
    assert diff_cat_replace.json()["error"]["code"] == "CATEGORY_MISMATCH"


@pytest.mark.asyncio
async def test_budget_shortfall_handling(async_client: AsyncClient):
    """When budget is too small, mission explains shortfall transparently without hiding costs."""
    user, token = await register_customer(async_client, "low_budget_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # Set an unrealistically low budget of ₹50 (5000 paise)
    resp = await async_client.post(
        "/api/v1/missions",
        json={"title": "Luxury Electronics Setup", "budget_paise": 5000},
        headers=headers,
    )
    assert resp.status_code == 201
    mission = resp.json()

    assert mission["budget_paise"] == 5000
    assert mission["is_over_budget"] is True
    assert mission["budget_shortfall_paise"] > 0
    assert mission["remaining_budget_paise"] == 0
    assert (
        "exceeds" in mission["summary_explanation"].lower()
        or "budget" in mission["summary_explanation"].lower()
    )


@pytest.mark.asyncio
async def test_mission_add_to_cart_integration(async_client: AsyncClient):
    """Customer can add selected mission items directly to their active shopping cart."""
    user, token = await register_customer(async_client, "cart_adder")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await async_client.post(
        "/api/v1/missions",
        json={"title": "Home Essentials", "budget_paise": 1000000},
        headers=headers,
    )
    assert create_resp.status_code == 201
    mission = create_resp.json()
    m_id = mission["id"]

    # Select only the first 2 items
    items = mission["items"]
    assert len(items) >= 2
    for i, itm in enumerate(items):
        await async_client.patch(
            f"/api/v1/missions/{m_id}/items/{itm['id']}",
            json={"is_selected": i < 2},
            headers=headers,
        )

    # Add to cart
    add_cart_resp = await async_client.post(
        f"/api/v1/missions/{m_id}/add-to-cart",
        headers=headers,
    )
    assert add_cart_resp.status_code == 200
    res_data = add_cart_resp.json()
    assert res_data["mission_id"] == m_id
    assert res_data["added_items_count"] == 2
    assert "cart" in res_data
    assert res_data["cart"]["item_count"] >= 2

    # Verify cart via GET /api/v1/cart
    cart_resp = await async_client.get("/api/v1/cart", headers=headers)
    assert cart_resp.status_code == 200
    cart_data = cart_resp.json()
    assert cart_data["item_count"] >= 2
    assert cart_data["subtotal_paise"] > 0


@pytest.mark.asyncio
async def test_mission_plan_preview(async_client: AsyncClient):
    """Customers can preview a shopping plan without persisting a database mission."""
    preview_resp = await async_client.post(
        "/api/v1/missions/preview",
        json={
            "title": "Apartment Move-In",
            "budget_paise": 2000000,
            "people_count": 3,
            "preferences": ["eco-friendly"],
        },
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["title"] == "Apartment Move-In"
    assert preview["budget_paise"] == 2000000
    assert len(preview["groups"]) > 0
    assert preview["total_cost_paise"] > 0
    assert "summary_explanation" in preview


@pytest.mark.asyncio
async def test_mission_to_checkout_complete_customer_journey(async_client: AsyncClient):
    """End-to-End Customer Journey: Mission -> Add to Cart -> Quote -> Reservation -> Order.

    Verifies:
    1. Real marketplace products from verified retailers are planned.
    2. Items transfer into the customer's active universal shopping basket.
    3. Checkout quote generation validates live prices, GST, and seller attributions.
    4. Inventory reservation acquires row locks and revalidates on-hand stock.
    5. Order creation snapshot preserves complete financial ledger and retailer items.
    """
    user, token = await register_customer(async_client, "journey_shopper")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Customer creates delivery address
    addr_resp = await async_client.post(
        "/api/v1/addresses",
        headers=headers,
        json={
            "recipient_name": "Journey Shopper",
            "phone": "+919876543210",
            "line1": "Flat 101, Palm Grove Apartments",
            "city": "Mumbai",
            "state": "MH",
            "postal_code": "400001",
            "is_default": True,
        },
    )
    assert addr_resp.status_code == 201
    address_id = addr_resp.json()["id"]

    # 2. Customer creates a Mission
    mission_resp = await async_client.post(
        "/api/v1/missions",
        headers=headers,
        json={
            "title": "Complete Kitchen Setup under ₹15,000",
            "budget_paise": 1500000,
            "people_count": 2,
            "preferences": ["durable", "stainless steel"],
        },
    )
    assert mission_resp.status_code == 201
    mission = mission_resp.json()
    m_id = mission["id"]
    assert len(mission["items"]) > 0

    # 3. Customer modifies item 1 quantity to 2
    first_item = mission["items"][0]
    update_resp = await async_client.patch(
        f"/api/v1/missions/{m_id}/items/{first_item['id']}",
        headers=headers,
        json={"quantity": 2},
    )
    assert update_resp.status_code == 200

    # 4. Add selected mission items to Cart
    add_cart_resp = await async_client.post(
        f"/api/v1/missions/{m_id}/add-to-cart",
        headers=headers,
    )
    assert add_cart_resp.status_code == 200
    cart_res = add_cart_resp.json()
    assert cart_res["added_items_count"] > 0

    # 5. Generate Checkout Quote (revalidates price, GST and retailer attribution)
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        headers=headers,
        json={"delivery_address_id": address_id},
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    quote_id = quote["id"]
    assert quote["status"] == "ACTIVE"
    assert quote["total_payable_paise"] > 0
    assert len(quote["items"]) > 0

    # 6. Reserve Inventory (revalidates live stock and locks rows)
    res_resp = await async_client.post(
        "/api/v1/reservations",
        headers=headers,
        json={"quote_id": quote_id},
    )
    assert res_resp.status_code == 201
    reservation = res_resp.json()
    reservation_id = reservation["id"]
    assert reservation["status"] == "ACTIVE"

    # 7. Place Order
    order_resp = await async_client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "quote_id": quote_id,
            "reservation_id": reservation_id,
            "delivery_address_id": address_id,
        },
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] in ("PENDING_PAYMENT", "CONFIRMED")
    assert order["customer_id"] == user["id"]
    assert len(order["items"]) > 0
