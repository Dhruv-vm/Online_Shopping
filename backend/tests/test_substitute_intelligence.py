import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

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
from app.modules.pricing.models import CheckoutQuote, QuoteStatus

_created_test_listing_ids: set[uuid.UUID] = set()


def make_retailer(
    name: str,
    slug: str,
    rating: float = 4.8,
    verification_status: str = "VERIFIED",
    is_active: bool = True,
) -> Retailer:
    return Retailer(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        rating=rating,
        state="MH",
        state_source="STATUTORY",
        verification_status=verification_status,
        is_active=is_active,
    )


@pytest.fixture(autouse=True)
async def cleanup_test_substitute_listings():
    assert settings.ENVIRONMENT != "production", (
        "Substitute intelligence tests cannot run against production environment"
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
    async_client: AsyncClient, prefix: str = "sub_user"
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
    on_hand_quantity: int = 20,
    reserved_quantity: int = 0,
    hsn_code: str = "8518",
    gst_rate_basis_points: int = 1800,
    is_active: bool = True,
) -> dict:
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        product = Product(
            id=uuid.uuid4(),
            category_id=category_id,
            name=product_name,
            slug=f"prod-{suffix}",
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
            hsn_code=hsn_code,
            gst_rate_basis_points=gst_rate_basis_points,
            tax_classification_source="STATUTORY",
            is_tax_verified=True,
            is_active=is_active,
        )
        session.add(listing)
        await session.flush()

        inventory = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing.id,
            on_hand_quantity=on_hand_quantity,
            reserved_quantity=reserved_quantity,
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
async def test_substitute_discovery_and_classification_tiers(
    async_client: AsyncClient,
):
    """
    Verifies that SubstituteService discovers, compares specifications, and classifies
    genuine alternatives into the 5 core substitute tiers:
    CLOSEST_MATCH, BUDGET_FRIENDLY, BETTER_VALUE, PREMIUM_UPGRADE, and AVAILABLE_NOW.
    """
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]

    # Create category and verified retailers
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Smartphones {suffix}",
            slug=f"smartphones-{suffix}",
            is_active=True,
        )
        session.add(cat)

        ret_a = make_retailer(
            f"Alpha Retail {suffix}", f"alpha-retail-{suffix}", rating=4.9
        )
        ret_b = make_retailer(
            f"Beta Store {suffix}", f"beta-store-{suffix}", rating=4.2
        )
        session.add_all([ret_a, ret_b])
        await session.commit()

    cat_id = cat.id
    ret_a_id = ret_a.id
    ret_b_id = ret_b.id

    # Original product listing: Apple iPhone 15, 128GB, Blue - ₹70,000
    orig = await create_custom_listing(
        category_id=cat_id,
        retailer_id=ret_a_id,
        product_name="Apple iPhone 15",
        brand="Apple",
        attributes={"storage": "128GB", "ram": "6GB", "color": "Blue"},
        selling_price_paise=7000000,
        original_price_paise=7990000,
        on_hand_quantity=10,
    )

    # Candidate 1: Apple iPhone 15 (Black) from Beta Store - ₹69,500 (Closest Match)
    cand_closest = await create_custom_listing(
        category_id=cat_id,
        retailer_id=ret_b_id,
        product_name="Apple iPhone 15",
        brand="Apple",
        attributes={"storage": "128GB", "ram": "6GB", "color": "Black"},
        selling_price_paise=6950000,
        original_price_paise=7990000,
        on_hand_quantity=15,
    )

    # Candidate 2: Samsung Galaxy S23 - ₹55,000 (Budget Friendly - 21.4% cheaper)
    cand_budget = await create_custom_listing(
        category_id=cat_id,
        retailer_id=ret_a_id,
        product_name="Samsung Galaxy S23",
        brand="Samsung",
        attributes={"storage": "128GB", "ram": "8GB", "color": "Cream"},
        selling_price_paise=5500000,
        original_price_paise=7499000,
        on_hand_quantity=20,
    )

    # Candidate 3: Apple iPhone 15 Pro, 256GB - ₹1,20,000 (Premium Upgrade)
    cand_upgrade = await create_custom_listing(
        category_id=cat_id,
        retailer_id=ret_b_id,
        product_name="Apple iPhone 15 Pro",
        brand="Apple",
        attributes={"storage": "256GB", "ram": "8GB", "color": "Titanium"},
        selling_price_paise=12000000,
        original_price_paise=13490000,
        on_hand_quantity=5,
    )

    # Query public substitute API
    resp = await async_client.get(f"/api/v1/substitutes/listings/{orig['listing_id']}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["original_listing_id"] == str(orig["listing_id"])
    assert data["original_brand"] == "Apple"
    assert data["total_count"] >= 3

    substitutes = {sub["listing_id"]: sub for sub in data["substitutes"]}
    assert str(cand_closest["listing_id"]) in substitutes
    assert str(cand_budget["listing_id"]) in substitutes
    assert str(cand_upgrade["listing_id"]) in substitutes

    # Verify candidate specs and pricing breakdowns
    sub_closest = substitutes[str(cand_closest["listing_id"])]
    assert "CLOSEST_MATCH" in sub_closest["applicable_types"]
    assert any("Brand: Apple" in s for s in sub_closest["matching_specs"])
    assert any("Storage: 128GB" in s for s in sub_closest["matching_specs"])
    assert any("Color" in s for s in sub_closest["differing_specs"])
    assert sub_closest["similarity_score"] >= 0.70

    sub_budget = substitutes[str(cand_budget["listing_id"])]
    assert "BUDGET_FRIENDLY" in sub_budget["applicable_types"]
    assert sub_budget["savings_percentage"] > 20.0
    assert sub_budget["price_diff_paise"] < 0

    sub_up = substitutes[str(cand_upgrade["listing_id"])]
    assert "PREMIUM_UPGRADE" in sub_up["applicable_types"]
    assert sub_up["price_diff_paise"] > 0

    # Test filtering by substitute type
    filter_resp = await async_client.get(
        f"/api/v1/substitutes/listings/{orig['listing_id']}?type=BUDGET_FRIENDLY"
    )
    assert filter_resp.status_code == 200
    filtered_data = filter_resp.json()
    assert all(
        "BUDGET_FRIENDLY" in s["applicable_types"] for s in filtered_data["substitutes"]
    )


@pytest.mark.asyncio
async def test_substitute_available_now_when_original_out_of_stock(
    async_client: AsyncClient,
):
    """When the original product is out of stock, in-stock alternatives are tagged AVAILABLE_NOW."""
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]

    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Audio {suffix}",
            slug=f"audio-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Audio Mart {suffix}",
            f"audio-mart-{suffix}",
            rating=4.7,
        )
        session.add_all([cat, ret])
        await session.commit()

    # Original product is OUT OF STOCK (on_hand = 0)
    orig = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Sony WH-1000XM5",
        brand="Sony",
        attributes={"anc": "Yes", "battery": "30h"},
        selling_price_paise=2699000,
        original_price_paise=2999000,
        on_hand_quantity=0,
    )

    # In-stock substitute
    cand = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Bose QuietComfort 45",
        brand="Bose",
        attributes={"anc": "Yes", "battery": "24h"},
        selling_price_paise=2599000,
        original_price_paise=2999000,
        on_hand_quantity=12,
    )

    resp = await async_client.get(f"/api/v1/substitutes/listings/{orig['listing_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trigger_reason"] == "OUT_OF_STOCK"
    assert data["original_is_in_stock"] is False
    assert len(data["substitutes"]) >= 1

    cand_sub = data["substitutes"][0]
    assert cand_sub["listing_id"] == str(cand["listing_id"])
    assert "AVAILABLE_NOW" in cand_sub["applicable_types"]
    assert cand_sub["substitute_type"] == "AVAILABLE_NOW"
    assert cand_sub["is_in_stock"] is True


@pytest.mark.asyncio
async def test_substitute_excludes_unverified_and_inactive_retailers(
    async_client: AsyncClient,
):
    """Substitute engine must never suggest listings from unverified or inactive retailers."""
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]

    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Laptops {suffix}",
            slug=f"laptops-{suffix}",
            is_active=True,
        )
        verified_ret = make_retailer(
            f"Verified Store {suffix}",
            f"verified-store-{suffix}",
            rating=4.5,
        )
        unverified_ret = make_retailer(
            f"Unverified Store {suffix}",
            f"unverified-store-{suffix}",
            rating=3.0,
            verification_status="PENDING",
        )
        inactive_ret = make_retailer(
            f"Inactive Store {suffix}",
            f"inactive-store-{suffix}",
            rating=4.0,
            is_active=False,
        )
        session.add_all([cat, verified_ret, unverified_ret, inactive_ret])
        await session.commit()

    orig = await create_custom_listing(
        category_id=cat.id,
        retailer_id=verified_ret.id,
        product_name="MacBook Air M2",
        brand="Apple",
        attributes={"ram": "8GB", "ssd": "256GB"},
        selling_price_paise=9990000,
        original_price_paise=11490000,
    )

    # Valid substitute
    cand_valid = await create_custom_listing(
        category_id=cat.id,
        retailer_id=verified_ret.id,
        product_name="MacBook Air M3",
        brand="Apple",
        attributes={"ram": "16GB", "ssd": "512GB"},
        selling_price_paise=12490000,
        original_price_paise=13490000,
    )

    # Invalid substitute: unverified retailer
    cand_unverified = await create_custom_listing(
        category_id=cat.id,
        retailer_id=unverified_ret.id,
        product_name="MacBook Air M2 Silver",
        brand="Apple",
        attributes={"ram": "8GB", "ssd": "256GB"},
        selling_price_paise=9500000,
        original_price_paise=11490000,
    )

    # Invalid substitute: inactive retailer
    cand_inactive = await create_custom_listing(
        category_id=cat.id,
        retailer_id=inactive_ret.id,
        product_name="Dell XPS 13",
        brand="Dell",
        attributes={"ram": "16GB", "ssd": "512GB"},
        selling_price_paise=10500000,
        original_price_paise=12000000,
    )

    resp = await async_client.get(f"/api/v1/substitutes/listings/{orig['listing_id']}")
    assert resp.status_code == 200
    listing_ids = [s["listing_id"] for s in resp.json()["substitutes"]]

    assert str(cand_valid["listing_id"]) in listing_ids
    assert str(cand_unverified["listing_id"]) not in listing_ids
    assert str(cand_inactive["listing_id"]) not in listing_ids


@pytest.mark.asyncio
async def test_substitute_strict_category_isolation(async_client: AsyncClient):
    """Substitutes must strictly belong to the same category."""
    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]

    async with session_factory() as session:
        cat_books = Category(
            id=uuid.uuid4(),
            name=f"Books {suffix}",
            slug=f"books-{suffix}",
            is_active=True,
        )
        cat_shoes = Category(
            id=uuid.uuid4(),
            name=f"Shoes {suffix}",
            slug=f"shoes-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Universal Retail {suffix}",
            f"univ-ret-{suffix}",
        )
        session.add_all([cat_books, cat_shoes, ret])
        await session.commit()

    book_listing = await create_custom_listing(
        category_id=cat_books.id,
        retailer_id=ret.id,
        product_name="Design Patterns Book",
        brand="Addison-Wesley",
        attributes={"pages": "395"},
        selling_price_paise=150000,
        original_price_paise=200000,
    )

    shoe_listing = await create_custom_listing(
        category_id=cat_shoes.id,
        retailer_id=ret.id,
        product_name="Running Shoes",
        brand="Nike",
        attributes={"size": "10"},
        selling_price_paise=499900,
        original_price_paise=599900,
    )

    resp = await async_client.get(
        f"/api/v1/substitutes/listings/{book_listing['listing_id']}"
    )
    assert resp.status_code == 200
    listing_ids = [s["listing_id"] for s in resp.json()["substitutes"]]
    assert str(shoe_listing["listing_id"]) not in listing_ids


@pytest.mark.asyncio
async def test_cart_item_substitutes_and_idor_protection(
    async_client: AsyncClient,
):
    """Customer can inspect substitutes for their active cart items; cross-customer IDOR is rejected."""
    user_a, token_a = await register_user(async_client, "cart_owner_a")
    user_b, token_b = await register_user(async_client, "cart_owner_b")

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Kitchen {suffix}",
            slug=f"kitchen-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Kitchen King {suffix}",
            f"kitchen-king-{suffix}",
        )
        session.add_all([cat, ret])
        await session.commit()

    listing_a = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Non-stick Frying Pan 24cm",
        brand="Prestige",
        attributes={"diameter": "24cm", "coating": "Teflon"},
        selling_price_paise=120000,
        original_price_paise=150000,
    )
    # Alternative listing
    await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Non-stick Frying Pan 26cm",
        brand="Prestige",
        attributes={"diameter": "26cm", "coating": "Granite"},
        selling_price_paise=140000,
        original_price_paise=180000,
    )

    # Customer A adds item to cart
    headers_a = {"Authorization": f"Bearer {token_a}"}
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_a["listing_id"]), "quantity": 1},
        headers=headers_a,
    )
    assert add_resp.status_code == 200
    cart_a = add_resp.json()
    item_a_id = cart_a["items"][0]["id"]

    # Customer A requests substitutes for their cart item
    sub_resp = await async_client.get(
        f"/api/v1/cart/items/{item_a_id}/substitutes",
        headers=headers_a,
    )
    assert sub_resp.status_code == 200
    assert len(sub_resp.json()["substitutes"]) >= 1

    # Customer B attempts IDOR to access Customer A's cart item substitutes
    headers_b = {"Authorization": f"Bearer {token_b}"}
    idor_resp = await async_client.get(
        f"/api/v1/cart/items/{item_a_id}/substitutes",
        headers=headers_b,
    )
    assert idor_resp.status_code == 404
    assert idor_resp.json()["error"]["code"] == "ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_cart_item_replace_happy_path_and_totals(
    async_client: AsyncClient,
):
    """Customer successfully replaces an item in their cart with an alternative listing."""
    _, token = await register_user(async_client, "replacer")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Fitness {suffix}",
            slug=f"fitness-{suffix}",
            is_active=True,
        )
        ret1 = make_retailer(
            f"Fit Store 1 {suffix}",
            f"fit-store-1-{suffix}",
        )
        ret2 = make_retailer(
            f"Fit Store 2 {suffix}",
            f"fit-store-2-{suffix}",
        )
        session.add_all([cat, ret1, ret2])
        await session.commit()

    # Original: Dumbbell 10kg from Retailer 1 - ₹1,500 (Qty: 2 -> ₹3,000)
    orig_listing = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret1.id,
        product_name="Cast Iron Dumbbell 10kg",
        brand="FitGym",
        attributes={"weight": "10kg", "material": "Cast Iron"},
        selling_price_paise=150000,
        original_price_paise=200000,
        on_hand_quantity=10,
    )

    # Substitute: Rubber Coated Dumbbell 10kg from Retailer 2 - ₹1,800
    sub_listing = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret2.id,
        product_name="Rubber Hex Dumbbell 10kg",
        brand="FitGym",
        attributes={"weight": "10kg", "material": "Rubber"},
        selling_price_paise=180000,
        original_price_paise=220000,
        on_hand_quantity=15,
    )

    # 1. Add original item
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(orig_listing["listing_id"]), "quantity": 2},
        headers=headers,
    )
    assert add_resp.status_code == 200
    cart_item_id = add_resp.json()["items"][0]["id"]
    assert add_resp.json()["subtotal_paise"] == 300000

    # 2. Replace item with substitute (preserving quantity 2)
    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{cart_item_id}/replace",
        json={"new_listing_id": str(sub_listing["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 200
    replace_data = replace_resp.json()
    assert replace_data["message"] == "Item successfully replaced in your basket."

    updated_cart = replace_data["cart"]
    assert updated_cart["item_count"] == 1
    assert updated_cart["total_quantity"] == 2
    # New subtotal: 2 * 180000 = 360000
    assert updated_cart["subtotal_paise"] == 360000
    assert updated_cart["items"][0]["listing_id"] == str(sub_listing["listing_id"])
    assert updated_cart["items"][0]["retailer_id"] == str(ret2.id)
    assert updated_cart["retailers"][0]["retailer_id"] == str(ret2.id)


@pytest.mark.asyncio
async def test_cart_item_replace_merges_when_target_already_in_cart(
    async_client: AsyncClient,
):
    """When the substitute listing is already present in the cart, quantities merge up to max 10."""
    _, token = await register_user(async_client, "merger")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Beverages {suffix}",
            slug=f"beverages-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Beverage Mart {suffix}",
            f"bev-mart-{suffix}",
        )
        session.add_all([cat, ret])
        await session.commit()

    tea_a = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Green Tea Leaves 100g",
        brand="TeaBrand",
        attributes={"type": "Green"},
        selling_price_paise=20000,
        original_price_paise=25000,
        on_hand_quantity=20,
    )
    tea_b = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Assam Black Tea 100g",
        brand="TeaBrand",
        attributes={"type": "Black"},
        selling_price_paise=18000,
        original_price_paise=22000,
        on_hand_quantity=20,
    )

    # Add Tea A (qty 3) and Tea B (qty 2) to cart
    add_a = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(tea_a["listing_id"]), "quantity": 3},
        headers=headers,
    )
    item_a_id = add_a.json()["items"][0]["id"]

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(tea_b["listing_id"]), "quantity": 2},
        headers=headers,
    )

    # Now replace Tea A with Tea B
    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{item_a_id}/replace",
        json={"new_listing_id": str(tea_b["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 200
    cart = replace_resp.json()["cart"]

    # Cart now contains only 1 item (Tea B) with merged quantity: 3 + 2 = 5
    assert cart["item_count"] == 1
    assert cart["total_quantity"] == 5
    assert cart["items"][0]["listing_id"] == str(tea_b["listing_id"])
    assert cart["items"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_cart_item_replace_rejects_category_mismatch(
    async_client: AsyncClient,
):
    """Cart item replacement rejects target listings belonging to a different category."""
    _, token = await register_user(async_client, "cat_mismatch")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat_tech = Category(
            id=uuid.uuid4(),
            name=f"Tech {suffix}",
            slug=f"tech-{suffix}",
            is_active=True,
        )
        cat_food = Category(
            id=uuid.uuid4(),
            name=f"Food {suffix}",
            slug=f"food-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Mega Store {suffix}",
            f"mega-store-{suffix}",
        )
        session.add_all([cat_tech, cat_food, ret])
        await session.commit()

    item_tech = await create_custom_listing(
        category_id=cat_tech.id,
        retailer_id=ret.id,
        product_name="USB-C Hub",
        brand="Anker",
        attributes={"ports": "7"},
        selling_price_paise=350000,
        original_price_paise=400000,
    )
    item_food = await create_custom_listing(
        category_id=cat_food.id,
        retailer_id=ret.id,
        product_name="Almonds 500g",
        brand="NutZone",
        attributes={"weight": "500g"},
        selling_price_paise=60000,
        original_price_paise=70000,
    )

    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(item_tech["listing_id"]), "quantity": 1},
        headers=headers,
    )
    item_id = add_resp.json()["items"][0]["id"]

    # Attempt to replace Tech item with Food item
    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{item_id}/replace",
        json={"new_listing_id": str(item_food["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 400
    assert replace_resp.json()["error"]["code"] == "CATEGORY_MISMATCH"


@pytest.mark.asyncio
async def test_cart_item_replace_supersedes_active_quotes(
    async_client: AsyncClient,
):
    """Replacing an item in the cart supersedes active checkout quotes for that cart."""
    user, token = await register_user(async_client, "quote_invalidator")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Apparel {suffix}",
            slug=f"apparel-{suffix}",
            is_active=True,
        )
        ret = Retailer(
            id=uuid.uuid4(),
            name=f"Fashion Hub {suffix}",
            slug=f"fashion-hub-{suffix}",
            state="MH",
            state_source="STATUTORY",
            verification_status="VERIFIED",
            is_active=True,
        )
        session.add_all([cat, ret])
        await session.commit()

    listing_a = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Cotton T-Shirt M",
        brand="Puma",
        attributes={"size": "M", "color": "Navy"},
        selling_price_paise=99900,
        original_price_paise=149900,
    )
    listing_b = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Cotton T-Shirt L",
        brand="Puma",
        attributes={"size": "L", "color": "Navy"},
        selling_price_paise=99900,
        original_price_paise=149900,
    )

    # 1. Add item to cart
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_a["listing_id"]), "quantity": 1},
        headers=headers,
    )
    item_id = add_resp.json()["items"][0]["id"]

    # 2. Generate a checkout quote
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={},
        headers=headers,
    )
    assert quote_resp.status_code == 201
    quote_id = uuid.UUID(quote_resp.json()["id"])

    # Verify quote is ACTIVE in DB
    async with session_factory() as session:
        q = (
            await session.execute(
                select(CheckoutQuote).where(CheckoutQuote.id == quote_id)
            )
        ).scalar_one()
        assert q.status == QuoteStatus.ACTIVE.value

    # 3. Replace item in cart
    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{item_id}/replace",
        json={"new_listing_id": str(listing_b["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 200

    # 4. Verify quote in DB is now SUPERSEDED
    async with session_factory() as session:
        q_after = (
            await session.execute(
                select(CheckoutQuote).where(CheckoutQuote.id == quote_id)
            )
        ).scalar_one()
        assert q_after.status == QuoteStatus.SUPERSEDED.value


@pytest.mark.asyncio
async def test_cart_item_replace_out_of_stock_rejected(
    async_client: AsyncClient,
):
    """Attempting to replace with an out-of-stock substitute returns 400 OUT_OF_STOCK."""
    _, token = await register_user(async_client, "oos_replacer")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Stationery {suffix}",
            slug=f"stationery-{suffix}",
            is_active=True,
        )
        ret = make_retailer(
            f"Office Store {suffix}",
            f"office-store-{suffix}",
        )
        session.add_all([cat, ret])
        await session.commit()

    in_stock_listing = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Gel Pen Blue 0.5mm",
        brand="Pilot",
        attributes={"tip": "0.5mm"},
        selling_price_paise=55000,
        original_price_paise=65000,
        on_hand_quantity=10,
    )
    oos_listing = await create_custom_listing(
        category_id=cat.id,
        retailer_id=ret.id,
        product_name="Gel Pen Black 0.5mm",
        brand="Pilot",
        attributes={"tip": "0.5mm"},
        selling_price_paise=55000,
        original_price_paise=65000,
        on_hand_quantity=0,
    )

    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(in_stock_listing["listing_id"]), "quantity": 1},
        headers=headers,
    )
    item_id = add_resp.json()["items"][0]["id"]

    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{item_id}/replace",
        json={"new_listing_id": str(oos_listing["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 400
    assert replace_resp.json()["error"]["code"] == "OUT_OF_STOCK"


@pytest.mark.asyncio
async def test_cart_item_replace_unverified_retailer_rejected(
    async_client: AsyncClient,
):
    """Attempting to replace with an unverified retailer listing returns 400 ALTERNATIVE_NOT_AVAILABLE."""
    _, token = await register_user(async_client, "unverified_replacer")
    headers = {"Authorization": f"Bearer {token}"}

    session_factory = get_session_factory()
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Gardening {suffix}",
            slug=f"gardening-{suffix}",
            is_active=True,
        )
        verified_ret = make_retailer(
            f"Verified Garden {suffix}",
            f"verified-garden-{suffix}",
        )
        unverified_ret = make_retailer(
            f"Unverified Garden {suffix}",
            f"unverified-garden-{suffix}",
            verification_status="PENDING",
        )
        session.add_all([cat, verified_ret, unverified_ret])
        await session.commit()

    listing_valid = await create_custom_listing(
        category_id=cat.id,
        retailer_id=verified_ret.id,
        product_name="Plant Fertilizer 1L",
        brand="GreenThumb",
        attributes={"volume": "1L"},
        selling_price_paise=45000,
        original_price_paise=50000,
    )
    listing_unverified = await create_custom_listing(
        category_id=cat.id,
        retailer_id=unverified_ret.id,
        product_name="Plant Fertilizer 2L",
        brand="GreenThumb",
        attributes={"volume": "2L"},
        selling_price_paise=75000,
        original_price_paise=90000,
    )

    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_valid["listing_id"]), "quantity": 1},
        headers=headers,
    )
    item_id = add_resp.json()["items"][0]["id"]

    replace_resp = await async_client.post(
        f"/api/v1/cart/items/{item_id}/replace",
        json={"new_listing_id": str(listing_unverified["listing_id"])},
        headers=headers,
    )
    assert replace_resp.status_code == 400
    assert replace_resp.json()["error"]["code"] == "ALTERNATIVE_NOT_AVAILABLE"
