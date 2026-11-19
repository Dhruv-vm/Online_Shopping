import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductVariant,
    StoreInventory,
)


async def setup_retailer_account(
    async_client: AsyncClient, suffix: str = "", verified: bool = True
) -> tuple[dict, str, dict]:
    """Helper to register a retailer user account and return tokens and retailer context."""
    unique = uuid.uuid4().hex[:8]
    email = f"retailer_{unique}{suffix}@example.com"
    store_name = f"Test Store {unique}{suffix}"
    reg_resp = await async_client.post(
        "/api/v1/auth/retailer/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": f"Retailer Owner {unique}",
            "phone": "9876543210",
            "store_name": store_name,
            "state": "KA",
            "business_address": "123 Market Street, Bengaluru",
            "description": "Premium Electronics and Goods",
        },
    )
    assert reg_resp.status_code == 201
    auth_data = reg_resp.json()
    token = auth_data["access_token"]
    user = auth_data["user"]

    if verified:
        from sqlalchemy import update

        from app.modules.catalogue.models import Retailer

        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(
                update(Retailer)
                .where(Retailer.user_id == uuid.UUID(user["id"]))
                .values(verification_status="VERIFIED")
            )
            await session.commit()

    return user, token, auth_data


async def setup_customer_account(async_client: AsyncClient) -> tuple[dict, str]:
    """Helper to register a standard customer account."""
    unique = uuid.uuid4().hex[:8]
    email = f"customer_{unique}@example.com"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Test Customer",
            "phone": "9876543211",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return data["user"], data["access_token"]


async def get_or_create_test_variant() -> uuid.UUID:
    """Helper to ensure at least one canonical product and variant exists for listing tests."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(ProductVariant).where(ProductVariant.is_active.is_(True))
        variant = (await session.execute(stmt)).scalars().first()
        if variant:
            return variant.id

        # Create category, product, variant
        cat = Category(
            id=uuid.uuid4(),
            name="Retailer Test Category",
            slug=f"ret-test-cat-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        session.add(cat)
        await session.flush()

        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name="Universal Test Smartphone",
            slug=f"univ-test-phone-{uuid.uuid4().hex[:6]}",
            brand="BASKET Brands",
            is_active=True,
        )
        session.add(prod)
        await session.flush()

        var = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            name="128GB Midnight Black",
            sku=f"SKU-{uuid.uuid4().hex[:8].upper()}",
            attributes={"color": "Midnight Black", "storage": "128GB"},
            is_active=True,
        )
        session.add(var)
        await session.commit()
        return var.id


@pytest.mark.asyncio
async def test_retailer_listings_rbac_enforcement(async_client: AsyncClient):
    """Customer accounts cannot access retailer listing endpoints (HTTP 403 Forbidden)."""
    _cust, cust_token = await setup_customer_account(async_client)
    headers = {"Authorization": f"Bearer {cust_token}"}

    # 1. Customer listing read
    resp = await async_client.get("/api/v1/retailer/listings", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # 2. Customer listing creation
    variant_id = await get_or_create_test_variant()
    resp_create = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 200000,
            "selling_price_paise": 180000,
            "initial_on_hand_quantity": 25,
        },
    )
    assert resp_create.status_code == 403

    # 3. Customer inventory dashboard
    resp_inv = await async_client.get("/api/v1/retailer/inventory", headers=headers)
    assert resp_inv.status_code == 403


@pytest.mark.asyncio
async def test_retailer_catalogue_lookup_and_listing_creation(
    async_client: AsyncClient,
):
    """Retailer browses catalogue, selects a variant, and creates a store listing."""
    _user, token, _ = await setup_retailer_account(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    variant_id = await get_or_create_test_variant()

    # 1. Catalogue lookup
    cat_resp = await async_client.get(
        "/api/v1/retailer/catalogue/products", headers=headers
    )
    assert cat_resp.status_code == 200
    products = cat_resp.json()
    assert len(products) > 0

    # 2. Create listing
    create_payload = {
        "variant_id": str(variant_id),
        "seller_sku": "MY-STORE-SKU-01",
        "original_price_paise": 250000,
        "selling_price_paise": 229900,
        "hsn_code": "85171200",
        "gst_rate_basis_points": 1800,
        "is_active": True,
        "initial_on_hand_quantity": 40,
        "low_stock_threshold": 8,
    }
    resp = await async_client.post(
        "/api/v1/retailer/listings", headers=headers, json=create_payload
    )
    assert resp.status_code == 201
    listing = resp.json()
    listing_id = listing["id"]
    assert listing["seller_sku"] == "MY-STORE-SKU-01"
    assert listing["selling_price_paise"] == 229900
    assert listing["original_price_paise"] == 250000
    assert listing["inventory"]["on_hand_quantity"] == 40
    assert listing["inventory"]["available_quantity"] == 40
    assert listing["inventory"]["low_stock_threshold"] == 8
    assert listing["inventory"]["is_low_stock"] is False
    assert listing["inventory"]["is_out_of_stock"] is False

    # 3. Duplicate listing rejected
    dup_resp = await async_client.post(
        "/api/v1/retailer/listings", headers=headers, json=create_payload
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "LISTING_ALREADY_EXISTS"

    # 4. Catalogue lookup now flags variant as already listed
    cat_resp2 = await async_client.get(
        "/api/v1/retailer/catalogue/products", headers=headers
    )
    assert cat_resp2.status_code == 200
    all_vars = [v for p in cat_resp2.json() for v in p["variants"]]
    matched = next((v for v in all_vars if v["id"] == str(variant_id)), None)
    if matched:
        assert matched["is_already_listed"] is True
        assert matched["existing_listing_id"] == listing_id


@pytest.mark.asyncio
async def test_retailer_tenant_isolation_anti_idor(async_client: AsyncClient):
    """Retailer B cannot view, edit, or adjust inventory of Retailer A's listings."""
    # Retailer A setup & listing
    _user_a, token_a, _ = await setup_retailer_account(async_client, suffix="_a")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    variant_id = await get_or_create_test_variant()

    create_resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers_a,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 150000,
            "selling_price_paise": 120000,
            "initial_on_hand_quantity": 50,
            "low_stock_threshold": 5,
        },
    )
    assert create_resp.status_code == 201
    listing_a_id = create_resp.json()["id"]

    # Retailer B setup
    _user_b, token_b, _ = await setup_retailer_account(async_client, suffix="_b")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Retailer B cannot GET listing A
    get_resp = await async_client.get(
        f"/api/v1/retailer/listings/{listing_a_id}", headers=headers_b
    )
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "LISTING_NOT_FOUND"

    # 2. Retailer B cannot PUT listing A
    put_resp = await async_client.put(
        f"/api/v1/retailer/listings/{listing_a_id}",
        headers=headers_b,
        json={"selling_price_paise": 99900},
    )
    assert put_resp.status_code == 404
    assert put_resp.json()["error"]["code"] == "LISTING_NOT_FOUND"

    # 3. Retailer B cannot adjust inventory of listing A
    adj_resp = await async_client.post(
        f"/api/v1/retailer/listings/{listing_a_id}/inventory",
        headers=headers_b,
        json={"adjustment_type": "SET", "quantity": 0},
    )
    assert adj_resp.status_code == 404
    assert adj_resp.json()["error"]["code"] == "LISTING_NOT_FOUND"

    # 4. Retailer B cannot DELETE listing A
    del_resp = await async_client.delete(
        f"/api/v1/retailer/listings/{listing_a_id}",
        headers=headers_b,
    )
    assert del_resp.status_code == 404
    assert del_resp.json()["error"]["code"] == "LISTING_NOT_FOUND"

    # 5. Retailer B cannot bulk-adjust inventory for listing A
    bulk_resp = await async_client.post(
        "/api/v1/retailer/inventory/bulk-adjust",
        headers=headers_b,
        json={
            "items": [
                {
                    "listing_id": str(listing_a_id),
                    "on_hand_quantity": 999,
                    "low_stock_threshold": 1,
                }
            ]
        },
    )
    assert bulk_resp.status_code == 404
    assert bulk_resp.json()["error"]["code"] == "LISTING_NOT_FOUND"

    # 6. Listing A does not appear in Retailer B's listing feed
    list_b_resp = await async_client.get("/api/v1/retailer/listings", headers=headers_b)
    assert list_b_resp.status_code == 200
    items_b = list_b_resp.json()["items"]
    assert all(item["id"] != listing_a_id for item in items_b)

    # 7. Listing A's inventory does not appear in Retailer B's inventory console
    inv_b_resp = await async_client.get("/api/v1/retailer/inventory", headers=headers_b)
    assert inv_b_resp.status_code == 200
    inv_items_b = inv_b_resp.json()["items"]
    assert all(item["listing_id"] != listing_a_id for item in inv_items_b)


@pytest.mark.asyncio
async def test_retailer_pricing_validation(async_client: AsyncClient):
    """Validation rejects selling price greater than original MRP."""
    _user, token, _ = await setup_retailer_account(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    variant_id = await get_or_create_test_variant()

    # 1. Reject on creation (Pydantic model validator -> 422)
    resp_create = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 10000,
            "selling_price_paise": 15000,  # Invalid: selling > MRP
            "initial_on_hand_quantity": 10,
        },
    )
    assert resp_create.status_code == 422

    # 2. Create valid listing
    valid_resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 10000,
            "selling_price_paise": 9000,
            "initial_on_hand_quantity": 10,
        },
    )
    assert valid_resp.status_code == 201
    listing_id = valid_resp.json()["id"]

    # 3. Reject on update (Service business logic -> 400)
    resp_update = await async_client.put(
        f"/api/v1/retailer/listings/{listing_id}",
        headers=headers,
        json={"selling_price_paise": 12000},  # 12000 > current MRP 10000
    )
    assert resp_update.status_code == 400
    assert resp_update.json()["error"]["code"] == "INVALID_PRICING"

    # 4. Valid price update
    resp_valid_update = await async_client.put(
        f"/api/v1/retailer/listings/{listing_id}",
        headers=headers,
        json={"original_price_paise": 15000, "selling_price_paise": 11500},
    )
    assert resp_valid_update.status_code == 200
    assert resp_valid_update.json()["original_price_paise"] == 15000
    assert resp_valid_update.json()["selling_price_paise"] == 11500


@pytest.mark.asyncio
async def test_retailer_inventory_adjustments_and_reservations_safety(
    async_client: AsyncClient,
):
    """Inventory updates enforce non-negative stock and protect reserved customer holds."""
    _user, token, _ = await setup_retailer_account(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    variant_id = await get_or_create_test_variant()

    create_resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 50000,
            "selling_price_paise": 45000,
            "initial_on_hand_quantity": 30,
            "low_stock_threshold": 10,
        },
    )
    assert create_resp.status_code == 201
    listing_id = create_resp.json()["id"]

    # 1. Delta adjustment: +15
    adj_resp1 = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=headers,
        json={"adjustment_type": "DELTA", "quantity": 15},
    )
    assert adj_resp1.status_code == 200
    assert adj_resp1.json()["on_hand_quantity"] == 45
    assert adj_resp1.json()["available_quantity"] == 45

    # 2. Set adjustment: 20
    adj_resp2 = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=headers,
        json={"adjustment_type": "SET", "quantity": 20, "low_stock_threshold": 15},
    )
    assert adj_resp2.status_code == 200
    assert adj_resp2.json()["on_hand_quantity"] == 20
    assert adj_resp2.json()["low_stock_threshold"] == 15

    # 3. Negative adjustment rejected
    adj_neg = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=headers,
        json={"adjustment_type": "DELTA", "quantity": -50},
    )
    assert adj_neg.status_code == 400
    assert adj_neg.json()["error"]["code"] == "NEGATIVE_STOCK_NOT_ALLOWED"

    # 4. Simulate reserved customer holds in PostgreSQL
    session_factory = get_session_factory()
    async with session_factory() as session:
        inv = (
            await session.execute(
                select(StoreInventory).where(
                    StoreInventory.listing_id == uuid.UUID(listing_id)
                )
            )
        ).scalar_one()
        inv.reserved_quantity = 15  # Customer currently reserving 15 units
        await session.commit()

    # 5. Attempting to reduce on-hand below reserved hold fails with 409
    adj_below_reserved = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=headers,
        json={"adjustment_type": "SET", "quantity": 10},  # 10 < 15 reserved
    )
    assert adj_below_reserved.status_code == 409
    assert adj_below_reserved.json()["error"]["code"] == "CANNOT_REDUCE_BELOW_RESERVED"


@pytest.mark.asyncio
async def test_retailer_inventory_dashboard_and_overview_kpis(
    async_client: AsyncClient,
):
    """Inventory dashboard and overview KPIs accurately compute counts and alert filters."""
    _user, token, _ = await setup_retailer_account(async_client)
    headers = {"Authorization": f"Bearer {token}"}
    variant_id = await get_or_create_test_variant()

    # Create listing with stock below threshold (available = 5, threshold = 10)
    resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 80000,
            "selling_price_paise": 75000,
            "initial_on_hand_quantity": 5,
            "low_stock_threshold": 10,
        },
    )
    assert resp.status_code == 201

    # 1. Retailer Overview
    overview_resp = await async_client.get("/api/v1/retailer/overview", headers=headers)
    assert overview_resp.status_code == 200
    overview = overview_resp.json()
    assert overview["total_listings"] >= 1
    assert overview["active_listings"] >= 1
    assert overview["low_stock_alerts"] >= 1

    # 2. Inventory Dashboard with filter
    inv_resp = await async_client.get(
        "/api/v1/retailer/inventory?status_filter=LOW_STOCK", headers=headers
    )
    assert inv_resp.status_code == 200
    dash = inv_resp.json()
    assert dash["summary"]["low_stock_count"] >= 1
    assert any(item["is_low_stock"] for item in dash["items"])


@pytest.mark.asyncio
async def test_concurrent_inventory_adjustments_prevent_lost_updates_and_negative_stock(
    async_client: AsyncClient,
):
    """Concurrent inventory updates with row-level locks prevent lost updates and negative stock."""
    _user, token, _ = await setup_retailer_account(async_client, suffix="_conc")
    headers = {"Authorization": f"Bearer {token}"}
    variant_id = await get_or_create_test_variant()

    # Initial stock = 20
    resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 60000,
            "selling_price_paise": 55000,
            "initial_on_hand_quantity": 20,
            "low_stock_threshold": 5,
        },
    )
    assert resp.status_code == 201
    listing_id = resp.json()["id"]

    # 1. Test Concurrent Increments: 8 parallel +5 increments (total expected +40 -> 60)
    async def do_increment():
        return await async_client.post(
            f"/api/v1/retailer/listings/{listing_id}/inventory",
            headers=headers,
            json={"adjustment_type": "DELTA", "quantity": 5},
        )

    inc_results = await asyncio.gather(*(do_increment() for _ in range(8)))
    assert all(r.status_code == 200 for r in inc_results)

    # Check updated stock is exactly 20 + (8 * 5) = 60
    check_resp = await async_client.get(
        f"/api/v1/retailer/listings/{listing_id}", headers=headers
    )
    assert check_resp.status_code == 200
    assert check_resp.json()["inventory"]["on_hand_quantity"] == 60

    # 2. Test Concurrent Decrements with Potential Oversubscription:
    # Current stock is 60. Launch 8 parallel -10 decrements (requests total -80, which exceeds 60).
    # Exactly 6 must succeed (60 - 60 = 0), and 2 must be rejected with 400 (NEGATIVE_STOCK_NOT_ALLOWED).
    async def do_decrement():
        return await async_client.post(
            f"/api/v1/retailer/listings/{listing_id}/inventory",
            headers=headers,
            json={"adjustment_type": "DELTA", "quantity": -10},
        )

    dec_results = await asyncio.gather(*(do_decrement() for _ in range(8)))
    succeeded = [r for r in dec_results if r.status_code == 200]
    rejected = [r for r in dec_results if r.status_code == 400]

    assert len(succeeded) == 6
    assert len(rejected) == 2
    for r in rejected:
        assert r.json()["error"]["code"] == "NEGATIVE_STOCK_NOT_ALLOWED"

    # Verify final stock is exactly 0 and never went negative
    final_resp = await async_client.get(
        f"/api/v1/retailer/listings/{listing_id}", headers=headers
    )
    assert final_resp.status_code == 200
    assert final_resp.json()["inventory"]["on_hand_quantity"] == 0
    assert final_resp.json()["inventory"]["available_quantity"] == 0
    assert final_resp.json()["inventory"]["is_out_of_stock"] is True
