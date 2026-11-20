from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import settings
from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)

_created_test_listing_ids: set[uuid.UUID] = set()


@pytest.fixture(autouse=True)
async def cleanup_intent_test_listings():
    assert settings.ENVIRONMENT != "production", (
        "Intent memory tests cannot run against production environment"
    )
    yield
    session_factory = get_session_factory()
    if session_factory and _created_test_listing_ids:
        async with session_factory() as session:
            stmt = (
                update(ProductListing)
                .where(ProductListing.id.in_(list(_created_test_listing_ids)))
                .values(is_active=False)
            )
            await session.execute(stmt)
            await session.commit()
        _created_test_listing_ids.clear()


async def register_user(
    async_client: AsyncClient, prefix: str = "intent_user"
) -> tuple[dict, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": f"{prefix.capitalize()} Tester",
            "phone": f"+919{uuid.uuid4().int % 1000000000:09d}",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["user"], data["access_token"]


async def create_custom_listing(
    *,
    category_id: uuid.UUID,
    retailer_id: uuid.UUID,
    product_name: str,
    brand: str,
    attributes: dict,
    selling_price_paise: int,
    original_price_paise: int,
    on_hand_quantity: int = 30,
) -> dict:
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        product = Product(
            id=uuid.uuid4(),
            category_id=category_id,
            name=product_name,
            slug=f"intent-prod-{suffix}",
            brand=brand,
            is_active=True,
        )
        session.add(product)
        await session.flush()

        variant = ProductVariant(
            id=uuid.uuid4(),
            product_id=product.id,
            name="Default Variant",
            sku=f"SUB-SKU-{suffix}",
            attributes=attributes,
            is_active=True,
        )
        session.add(variant)
        await session.flush()

        listing = ProductListing(
            id=uuid.uuid4(),
            retailer_id=retailer_id,
            variant_id=variant.id,
            selling_price_paise=selling_price_paise,
            original_price_paise=original_price_paise,
            currency="INR",
            hsn_code="8518",
            gst_rate_basis_points=1800,
            tax_classification_source="STATUTORY",
            is_tax_verified=True,
            is_active=True,
        )
        session.add(listing)
        await session.flush()

        inventory = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing.id,
            on_hand_quantity=on_hand_quantity,
            reserved_quantity=0,
        )
        session.add(inventory)
        await session.commit()

        _created_test_listing_ids.add(listing.id)

        return {
            "listing_id": listing.id,
            "product_id": product.id,
            "variant_id": variant.id,
            "selling_price_paise": selling_price_paise,
        }


@pytest.mark.asyncio
async def test_preference_profile_lifecycle(async_client: AsyncClient):
    """Customer can view, create, and update preference profile; personalization defaults to disabled."""
    _user, token = await register_user(async_client, "prof_user")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. New customers have personalization disabled by default
    get_res = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["personalization_enabled"] is False
    assert data["preferred_brands"] == []

    # Overview also reports personalization disabled by default
    overview_res = await async_client.get("/api/v1/intent/overview", headers=headers)
    assert overview_res.status_code == 200
    assert overview_res.json()["personalization_enabled"] is False

    # 2. Saving preferences does not enable personalization
    payload_prefs_only = {
        "preferred_brands": ["Sony", "Apple", "Boat"],
        "preferred_categories": ["electronics"],
        "preferred_retailers": ["Basket Mart"],
        "preferred_price_range": {"min_paise": 100000, "max_paise": 5000000},
        "shopping_priorities": ["QUALITY", "LOWEST_PRICE"],
        "preferred_attributes": {"material": "cotton", "color": "black"},
    }
    put_res = await async_client.put(
        "/api/v1/intent/profile", headers=headers, json=payload_prefs_only
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["preferred_brands"] == ["Sony", "Apple", "Boat"]
    assert updated["preferred_price_range"]["max_paise"] == 5000000
    assert "QUALITY" in updated["shopping_priorities"]
    assert updated["personalization_enabled"] is False

    # 3. Explicit opt-in enables personalization
    opt_in_res = await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )
    assert opt_in_res.status_code == 200
    assert opt_in_res.json()["personalization_enabled"] is True

    # Check profile confirms personalization is now enabled
    prof_after = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert prof_after.json()["personalization_enabled"] is True

    # 4. Editing preferences while opted in preserves explicit opt-in
    edit_res = await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={"preferred_brands": ["Sony", "Apple", "Boat", "Sennheiser"]},
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["personalization_enabled"] is True


@pytest.mark.asyncio
async def test_personalization_consent_toggle(async_client: AsyncClient):
    """Customer must explicitly opt-in to enable personalization, and can opt-out at any time."""
    _user, token = await register_user(async_client, "consent_user")
    headers = {"Authorization": f"Bearer {token}"}

    # Initial state is False
    prof_res = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert prof_res.json()["personalization_enabled"] is False

    # Explicit opt-in enables personalization
    patch_res = await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["personalization_enabled"] is True

    # Check profile reflects enabled state
    prof_res2 = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert prof_res2.json()["personalization_enabled"] is True

    # Opt-out disables personalization
    patch_res2 = await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": False},
    )
    assert patch_res2.status_code == 200
    assert patch_res2.json()["personalization_enabled"] is False

    # Check profile reflects disabled state
    prof_res3 = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert prof_res3.json()["personalization_enabled"] is False


@pytest.mark.asyncio
async def test_recurring_intentions_crud(async_client: AsyncClient):
    """Customer can create, list, update, toggle status, and delete recurring shopping intentions."""
    _user, token = await register_user(async_client, "recur_user")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create recurring intention
    create_payload = {
        "title": "Monthly Office Pantry Restock",
        "category_ids": ["grocery-food"],
        "frequency": "MONTHLY",
        "budget_paise": 600000,
        "notes": "Coffee beans, tea bags, oat milk, and healthy snacks",
    }
    create_res = await async_client.post(
        "/api/v1/intent/recurring", headers=headers, json=create_payload
    )
    assert create_res.status_code == 201
    intention = create_res.json()
    intention_id = intention["id"]
    assert intention["title"] == "Monthly Office Pantry Restock"
    assert intention["frequency"] == "MONTHLY"
    assert intention["is_active"] is True

    # 2. List intentions
    list_res = await async_client.get("/api/v1/intent/recurring", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(i["id"] == intention_id for i in items)

    # 3. Update intention
    update_res = await async_client.put(
        f"/api/v1/intent/recurring/{intention_id}",
        headers=headers,
        json={"title": "Bi-Weekly Office Pantry Restock", "frequency": "BIWEEKLY"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Bi-Weekly Office Pantry Restock"
    assert update_res.json()["frequency"] == "BIWEEKLY"

    # 4. Toggle status to paused
    pause_res = await async_client.patch(
        f"/api/v1/intent/recurring/{intention_id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["is_active"] is False

    # 5. Delete intention
    del_res = await async_client.delete(
        f"/api/v1/intent/recurring/{intention_id}", headers=headers
    )
    assert del_res.status_code == 204

    # Verify deleted
    list_after = await async_client.get("/api/v1/intent/recurring", headers=headers)
    assert all(i["id"] != intention_id for i in list_after.json())


@pytest.mark.asyncio
async def test_intent_memory_items_crud(async_client: AsyncClient):
    """Customer can add, list, and delete individual intent memory items."""
    _user, token = await register_user(async_client, "mem_card_user")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create memory item
    create_payload = {
        "memory_type": "PREFERENCE",
        "key": "eco_packaging",
        "value": {"packaging": "minimal_cardboard"},
        "summary": "Prefers plastic-free, recyclable packaging for all orders",
        "source": "CUSTOMER_STATED",
    }
    create_res = await async_client.post(
        "/api/v1/intent/memories", headers=headers, json=create_payload
    )
    assert create_res.status_code == 201
    memory = create_res.json()
    memory_id = memory["id"]
    assert memory["key"] == "eco_packaging"
    assert "plastic-free" in memory["summary"]

    # 2. List memories
    list_res = await async_client.get("/api/v1/intent/memories", headers=headers)
    assert list_res.status_code == 200
    memories = list_res.json()
    assert any(m["id"] == memory_id for m in memories)

    # 3. Delete memory
    del_res = await async_client.delete(
        f"/api/v1/intent/memories/{memory_id}", headers=headers
    )
    assert del_res.status_code == 204

    # Verify deleted
    list_after = await async_client.get("/api/v1/intent/memories", headers=headers)
    assert all(m["id"] != memory_id for m in list_after.json())


@pytest.mark.asyncio
async def test_clear_all_memories(async_client: AsyncClient):
    """Customer can clear all memories; subsequent profile creation defaults to personalization disabled."""
    _user, token = await register_user(async_client, "clear_user")
    headers = {"Authorization": f"Bearer {token}"}

    # Explicitly opt-in and add preference
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )
    await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={"preferred_brands": ["Samsung"]},
    )
    # Add a recurring intention
    await async_client.post(
        "/api/v1/intent/recurring",
        headers=headers,
        json={"title": "Household restock", "frequency": "MONTHLY"},
    )
    # Add a memory card
    await async_client.post(
        "/api/v1/intent/memories",
        headers=headers,
        json={"key": "test_key", "summary": "Test memory note"},
    )

    # Verify profile was opted in and had data
    pre_overview = await async_client.get("/api/v1/intent/overview", headers=headers)
    assert pre_overview.json()["personalization_enabled"] is True
    assert len(pre_overview.json()["recurring_intentions"]) == 1
    assert len(pre_overview.json()["memories"]) == 1

    # Clear all
    clear_res = await async_client.delete("/api/v1/intent/clear-all", headers=headers)
    assert clear_res.status_code == 204

    # Check overview is completely empty and personalization is disabled
    overview_res = await async_client.get("/api/v1/intent/overview", headers=headers)
    assert overview_res.status_code == 200
    ov = overview_res.json()
    assert ov["profile"] is None
    assert ov["recurring_intentions"] == []
    assert ov["memories"] == []
    assert ov["personalization_enabled"] is False

    # Subsequent new profile must default to personalization disabled
    new_prof_res = await async_client.get("/api/v1/intent/profile", headers=headers)
    assert new_prof_res.status_code == 200
    new_profile = new_prof_res.json()
    assert new_profile["personalization_enabled"] is False


@pytest.mark.asyncio
async def test_customer_isolation_and_anti_idor(async_client: AsyncClient):
    """Customer A cannot read or mutate Customer B's recurring intentions or memories."""
    _user_a, token_a = await register_user(async_client, "cust_a")
    _user_b, token_b = await register_user(async_client, "cust_b")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Customer A creates intention
    res = await async_client.post(
        "/api/v1/intent/recurring",
        headers=headers_a,
        json={"title": "Secret Gift Shopping", "frequency": "SEASONAL"},
    )
    intention_id = res.json()["id"]

    # Customer B attempts to update Customer A's intention
    patch_res = await async_client.patch(
        f"/api/v1/intent/recurring/{intention_id}/status",
        headers=headers_b,
        json={"is_active": False},
    )
    assert patch_res.status_code == 404

    # Customer B attempts to delete Customer A's intention
    del_res = await async_client.delete(
        f"/api/v1/intent/recurring/{intention_id}", headers=headers_b
    )
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_intent_suggestions_for_mission_planning(async_client: AsyncClient):
    """GET /api/v1/intent/suggestions provides pre-fill recommendations only when opted-in."""
    _user, token = await register_user(async_client, "sug_user")
    headers = {"Authorization": f"Bearer {token}"}

    # Configure preferences and recurring intention without opting in
    await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={
            "preferred_brands": ["Prestige", "Hawkins"],
            "shopping_priorities": ["DURABILITY"],
            "preferred_price_range": {"max_paise": 1500000},
        },
    )
    await async_client.post(
        "/api/v1/intent/recurring",
        headers=headers,
        json={
            "title": "Kitchen Utensil Upgrades",
            "category_ids": ["home-kitchen"],
            "frequency": "SEASONAL",
            "budget_paise": 1500000,
        },
    )

    # 1. Before opt-in: suggestions are disabled and neutral
    sug_res1 = await async_client.get("/api/v1/intent/suggestions", headers=headers)
    assert sug_res1.status_code == 200
    assert sug_res1.json()["personalization_enabled"] is False
    assert sug_res1.json()["suggested_brands"] == []

    # 2. Explicit opt-in enables suggestions
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )

    sug_res2 = await async_client.get("/api/v1/intent/suggestions", headers=headers)
    assert sug_res2.status_code == 200
    data = sug_res2.json()
    assert "Prestige" in data["suggested_brands"]
    assert "DURABILITY" in data["suggested_priorities"]
    assert data["suggested_budget_paise"] == 1500000
    assert len(data["applicable_intentions"]) >= 1
    assert data["personalization_enabled"] is True


@pytest.mark.asyncio
async def test_substitute_recommendation_personalized_by_intent(
    async_client: AsyncClient,
):
    """Substitute discovery only applies preference boosts after explicit opt-in; opt-out removes them."""
    _user, token = await register_user(async_client, "sub_intent_user")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Audio Gear {suffix}",
            slug=f"audio-{suffix}",
            is_active=True,
        )
        ret = Retailer(
            id=uuid.uuid4(),
            name=f"Sound World {suffix}",
            slug=f"sound-world-{suffix}",
            state="MH",
            state_source="STATUTORY",
            verification_status="VERIFIED",
            is_active=True,
        )
        session.add_all([cat, ret])
        await session.commit()

    # Create original listing
    orig = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Generic Wireless Earbuds",
        brand="GenericAudio",
        attributes={"type": "In-Ear"},
        selling_price_paise=299900,
        original_price_paise=399900,
    )
    # Create substitute listing from preferred brand
    sub = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Noise Cancelling Earbuds",
        brand="PreferredSound",
        attributes={"type": "In-Ear"},
        selling_price_paise=279900,
        original_price_paise=349900,
    )

    # Save preference for "PreferredSound" (without opting in)
    await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={"preferred_brands": ["PreferredSound"]},
    )

    # Add original item to customer cart
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(orig["listing_id"]), "quantity": 1},
        headers=headers,
    )
    assert add_resp.status_code == 200
    item_id = add_resp.json()["items"][0]["id"]

    # 1. Before opt-in: substitute discovery is neutral, no personalization notes
    sub_resp1 = await async_client.get(
        f"/api/v1/cart/items/{item_id}/substitutes",
        headers=headers,
    )
    assert sub_resp1.status_code == 200
    matched1 = next(
        s
        for s in sub_resp1.json()["substitutes"]
        if s["listing_id"] == str(sub["listing_id"])
    )
    assert "PreferredSound" not in (matched1.get("compatibility_notes") or "")

    # 2. Explicit opt-in enables personalization
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )

    sub_resp2 = await async_client.get(
        f"/api/v1/cart/items/{item_id}/substitutes",
        headers=headers,
    )
    assert sub_resp2.status_code == 200
    matched2 = next(
        s
        for s in sub_resp2.json()["substitutes"]
        if s["listing_id"] == str(sub["listing_id"])
    )
    assert "PreferredSound" in matched2["compatibility_notes"]

    # 3. Opt-out immediately removes personalization notes
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": False},
    )

    sub_resp3 = await async_client.get(
        f"/api/v1/cart/items/{item_id}/substitutes",
        headers=headers,
    )
    assert sub_resp3.status_code == 200
    matched3 = next(
        s
        for s in sub_resp3.json()["substitutes"]
        if s["listing_id"] == str(sub["listing_id"])
    )
    assert "PreferredSound" not in (matched3.get("compatibility_notes") or "")


@pytest.mark.asyncio
async def test_disabled_personalization_omits_intent_influence(
    async_client: AsyncClient,
):
    """When customer disables personalization, suggestions and boosts are omitted."""
    _user, token = await register_user(async_client, "no_pers_user")
    headers = {"Authorization": f"Bearer {token}"}

    # Save preference and then disable personalization
    await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={
            "preferred_brands": ["Apple"],
            "personalization_enabled": False,
        },
    )

    sug_res = await async_client.get("/api/v1/intent/suggestions", headers=headers)
    assert sug_res.status_code == 200
    data = sug_res.json()
    assert data["personalization_enabled"] is False
    assert data["suggested_brands"] == []
    assert "disabled" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_mission_recommendation_personalized_by_intent(
    async_client: AsyncClient,
):
    """Missions only utilize intent profile preferred brands after explicit opt-in; opt-out reverts to neutral."""
    _user, token = await register_user(async_client, "mission_intent_user")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Home Gear {suffix}",
            slug=f"home-{suffix}",
            is_active=True,
        )
        ret = Retailer(
            id=uuid.uuid4(),
            name=f"Home Store {suffix}",
            slug=f"home-store-{suffix}",
            state="MH",
            state_source="STATUTORY",
            verification_status="VERIFIED",
            is_active=True,
        )
        session.add_all([cat, ret])
        await session.commit()

    # Create listing 1: generic brand
    await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Generic Blender",
        brand="GenericHome",
        attributes={"power": "500W"},
        selling_price_paise=199900,
        original_price_paise=249900,
    )
    # Create listing 2: preferred brand
    fav = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Chef Master Blender",
        brand="ChefMaster",
        attributes={"power": "750W"},
        selling_price_paise=219900,
        original_price_paise=299900,
    )

    # 1. Save preference profile with ChefMaster preferred (without opting in)
    await async_client.put(
        "/api/v1/intent/profile",
        headers=headers,
        json={"preferred_brands": ["ChefMaster"], "shopping_priorities": ["QUALITY"]},
    )

    # Before opt-in: mission does NOT cite saved preferred brand
    mission_resp1 = await async_client.post(
        "/api/v1/missions",
        headers=headers,
        json={
            "title": "Kitchen Upgrade Neutral",
            "category_id": str(cat.id),
            "budget_paise": 500000,
            "optimization_goal": "BALANCED",
        },
    )
    assert mission_resp1.status_code == 201
    for itm in mission_resp1.json()["items"]:
        assert "Matches your saved preferred brand" not in itm["recommendation_reason"]

    # 2. Explicit opt-in enables personalization
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": True},
    )

    # Create mission while opted in
    mission_resp2 = await async_client.post(
        "/api/v1/missions",
        headers=headers,
        json={
            "title": "Kitchen Upgrade Personalized",
            "category_id": str(cat.id),
            "budget_paise": 500000,
            "optimization_goal": "BALANCED",
        },
    )
    assert mission_resp2.status_code == 201
    mission_data = mission_resp2.json()
    items = mission_data["items"]
    assert len(items) > 0
    fav_item = next(
        (i for i in items if i["listing_id"] == str(fav["listing_id"])), None
    )
    assert fav_item is not None
    assert "ChefMaster" in fav_item["recommendation_reason"]

    # 3. Explicit opt-out reverts to neutral planning
    await async_client.patch(
        "/api/v1/intent/consent",
        headers=headers,
        json={"personalization_enabled": False},
    )

    mission_resp3 = await async_client.post(
        "/api/v1/missions",
        headers=headers,
        json={
            "title": "Kitchen Upgrade Neutral Again",
            "category_id": str(cat.id),
            "budget_paise": 500000,
            "optimization_goal": "BALANCED",
        },
    )
    assert mission_resp3.status_code == 201
    for itm in mission_resp3.json()["items"]:
        assert "Matches your saved preferred brand" not in itm["recommendation_reason"]
