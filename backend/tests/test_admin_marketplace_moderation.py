import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select, update

from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    RetailerVerificationDocument,
    StoreInventory,
)
from app.modules.identity.models import User
from app.modules.pricing.discount_service import DiscountService


async def create_user_with_role(
    async_client: AsyncClient,
    role: str = "customer",
) -> tuple[dict[str, str], dict]:
    """Helper to register a user with a specific role and return auth header and user dict."""
    unique = uuid.uuid4().hex[:8]
    email = f"{role}_{unique}@example.com"
    password = "TestPassword123!"

    if role == "retailer":
        store_name = f"Test Store {unique}"
        resp = await async_client.post(
            "/api/v1/auth/retailer/register",
            json={
                "email": email,
                "password": password,
                "full_name": f"Retailer Owner {unique}",
                "phone": "9876543210",
                "store_name": store_name,
                "state": "KA",
                "business_address": "123 Market Street, Bengaluru",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        token = data["access_token"]
        return {"Authorization": f"Bearer {token}"}, data["user"]

    # Customer registration
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": f"User {unique}",
            "phone": "9876543211",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    user = data["user"]

    if role == "admin":
        session_factory = get_session_factory()
        async with session_factory() as session:
            await session.execute(
                update(User)
                .where(User.id == uuid.UUID(user["id"]))
                .values(role="admin")
            )
            await session.commit()
        # Login again to get refreshed JWT containing admin role claim
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        user = login_resp.json()["user"]

    return {"Authorization": f"Bearer {token}"}, user


@pytest.mark.asyncio
async def test_admin_endpoints_rbac_enforcement(async_client: AsyncClient):
    """Customers and retailers cannot access admin endpoints (HTTP 403)."""
    cust_headers, _ = await create_user_with_role(async_client, role="customer")
    ret_headers, _ = await create_user_with_role(async_client, role="retailer")

    admin_endpoints = [
        ("GET", "/api/v1/admin/overview"),
        ("GET", "/api/v1/admin/retailers"),
        ("GET", "/api/v1/admin/catalogue/products"),
        ("GET", "/api/v1/admin/deals"),
    ]

    for method, path in admin_endpoints:
        # Customer access rejected
        resp_c = await async_client.request(method, path, headers=cust_headers)
        assert resp_c.status_code == 403, f"Customer allowed on {path}"
        assert resp_c.json()["error"]["code"] == "FORBIDDEN"

        # Retailer access rejected
        resp_r = await async_client.request(method, path, headers=ret_headers)
        assert resp_r.status_code == 403, f"Retailer allowed on {path}"
        assert resp_r.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_catalogue_management_and_pricing_isolation(
    async_client: AsyncClient,
):
    """Admin can create/edit canonical products and variants without altering retailer pricing."""
    admin_headers, _ = await create_user_with_role(async_client, role="admin")

    # 1. Create Category
    cat_resp = await async_client.post(
        "/api/v1/admin/catalogue/categories",
        headers=admin_headers,
        json={
            "name": f"Admin Test Electronics {uuid.uuid4().hex[:4]}",
            "description": "Electronics category created by Admin",
        },
    )
    assert cat_resp.status_code == 201
    cat_data = cat_resp.json()
    category_id = cat_data["id"]

    # 2. Create Canonical Product with initial variants
    unique = uuid.uuid4().hex[:6]
    sku_1 = f"ADM-SKU-{unique}-1"
    prod_resp = await async_client.post(
        "/api/v1/admin/catalogue/products",
        headers=admin_headers,
        json={
            "category_id": category_id,
            "name": f"Admin Flagship Smartphone {unique}",
            "brand": "BasketTech",
            "description": "Flagship canonical device",
            "image_urls": ["https://images.example.com/phone-front.jpg"],
            "variants": [
                {
                    "name": "128GB Titanium",
                    "sku": sku_1,
                    "attributes": {"storage": "128GB", "color": "Titanium"},
                }
            ],
        },
    )
    assert prod_resp.status_code == 201
    prod_data = prod_resp.json()
    product_id = prod_data["id"]
    variant_id = prod_data["variants"][0]["id"]
    assert prod_data["brand"] == "BasketTech"
    assert len(prod_data["variants"]) == 1

    # 3. Duplicate SKU rejected
    dup_sku_resp = await async_client.post(
        f"/api/v1/admin/catalogue/products/{product_id}/variants",
        headers=admin_headers,
        json={
            "name": "Another Variant with Same SKU",
            "sku": sku_1,
            "attributes": {"storage": "256GB"},
        },
    )
    assert dup_sku_resp.status_code == 409
    assert dup_sku_resp.json()["error"]["code"] == "DUPLICATE_SKU"

    # 4. Add second variant with distinct SKU
    sku_2 = f"ADM-SKU-{unique}-2"
    var2_resp = await async_client.post(
        f"/api/v1/admin/catalogue/products/{product_id}/variants",
        headers=admin_headers,
        json={
            "name": "256GB Titanium",
            "sku": sku_2,
            "attributes": {"storage": "256GB", "color": "Titanium"},
        },
    )
    assert var2_resp.status_code == 201
    assert var2_resp.json()["sku"] == sku_2

    # 5. Verified Retailer lists the variant and sets independent price
    ret_headers, ret_user = await create_user_with_role(async_client, role="retailer")
    # Mark retailer as VERIFIED so they can list
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(Retailer)
            .where(Retailer.user_id == uuid.UUID(ret_user["id"]))
            .values(verification_status="VERIFIED")
        )
        await session.commit()

    ret_listing_resp = await async_client.post(
        "/api/v1/retailer/listings",
        headers=ret_headers,
        json={
            "variant_id": variant_id,
            "original_price_paise": 8990000,
            "selling_price_paise": 7990000,
            "initial_on_hand_quantity": 25,
            "low_stock_threshold": 5,
        },
    )
    assert ret_listing_resp.status_code == 201
    listing_id = ret_listing_resp.json()["id"]

    # 6. Admin updates canonical product metadata (name, description, brand)
    prod_update_resp = await async_client.put(
        f"/api/v1/admin/catalogue/products/{product_id}",
        headers=admin_headers,
        json={
            "name": f"Admin Flagship Smartphone Pro {unique}",
            "brand": "BasketTech Prime",
            "description": "Updated canonical specification",
        },
    )
    assert prod_update_resp.status_code == 200
    assert prod_update_resp.json()["name"] == f"Admin Flagship Smartphone Pro {unique}"
    assert prod_update_resp.json()["brand"] == "BasketTech Prime"

    # 7. CRITICAL INVARIANT: Verify retailer listing price was NOT modified
    verify_listing_resp = await async_client.get(
        f"/api/v1/retailer/listings/{listing_id}",
        headers=ret_headers,
    )
    assert verify_listing_resp.status_code == 200
    assert verify_listing_resp.json()["selling_price_paise"] == 7990000
    assert verify_listing_resp.json()["original_price_paise"] == 8990000

    # 8. Deactivate product
    del_resp = await async_client.delete(
        f"/api/v1/admin/catalogue/products/{product_id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == 204

    # Get product verifies is_active is now False
    get_deactivated = await async_client.get(
        f"/api/v1/admin/catalogue/products/{product_id}",
        headers=admin_headers,
    )
    assert get_deactivated.status_code == 200
    assert get_deactivated.json()["is_active"] is False

    # Cleanup test listing
    async with session_factory() as session:
        await session.execute(
            delete(StoreInventory).where(
                StoreInventory.listing_id == uuid.UUID(listing_id)
            )
        )
        await session.execute(
            delete(ProductListing).where(ProductListing.id == uuid.UUID(listing_id))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_retailer_verification_workflow_and_enforcement(
    async_client: AsyncClient,
):
    """Admin approves, suspends, and reactivates retailer; unverified/suspended retailers cannot publish listings."""
    admin_headers, admin_user = await create_user_with_role(async_client, role="admin")

    # 1. Retailer registers (starts with PENDING verification)
    ret_headers, ret_user = await create_user_with_role(async_client, role="retailer")

    # Get retailer ID from database
    session_factory = get_session_factory()
    async with session_factory() as session:
        ret = (
            await session.execute(
                select(Retailer).where(Retailer.user_id == uuid.UUID(ret_user["id"]))
            )
        ).scalar_one()
        retailer_id = ret.id
        assert ret.verification_status == "PENDING"

        # Add a compliance document for this retailer
        doc = RetailerVerificationDocument(
            id=uuid.uuid4(),
            retailer_id=retailer_id,
            document_type="GST_CERTIFICATE",
            document_url="https://docs.example.com/gst-cert.pdf",
            status="PENDING",
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # 2. PENDING retailer attempts to create listing -> REJECTED 403
    # First ensure a canonical variant exists
    async with session_factory() as session:
        variant = (
            (
                await session.execute(
                    select(ProductVariant).where(ProductVariant.is_active.is_(True))
                )
            )
            .scalars()
            .first()
        )
        variant_id = variant.id

    unverified_attempt = await async_client.post(
        "/api/v1/retailer/listings",
        headers=ret_headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 100000,
            "selling_price_paise": 90000,
            "initial_on_hand_quantity": 10,
        },
    )
    assert unverified_attempt.status_code == 403
    assert unverified_attempt.json()["error"]["code"] == "RETAILER_NOT_VERIFIED"

    # 3. Admin inspects retailer details and document
    detail_resp = await async_client.get(
        f"/api/v1/admin/retailers/{retailer_id}",
        headers=admin_headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["verification_status"] == "PENDING"
    assert len(detail_data["documents"]) == 1
    assert detail_data["documents"][0]["document_type"] == "GST_CERTIFICATE"

    # 4. Admin verifies document
    doc_verify_resp = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/documents/{doc_id}/verify",
        headers=admin_headers,
        json={"status": "VERIFIED"},
    )
    assert doc_verify_resp.status_code == 200
    assert doc_verify_resp.json()["status"] == "VERIFIED"

    # 5. Admin approves retailer
    verify_resp = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        headers=admin_headers,
        json={"status": "VERIFIED"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verification_status"] == "VERIFIED"

    # Verification history recorded
    detail_after_approval = await async_client.get(
        f"/api/v1/admin/retailers/{retailer_id}",
        headers=admin_headers,
    )
    history = detail_after_approval.json()["verification_history"]
    assert len(history) >= 1
    assert history[0]["action"] == "APPROVED"
    assert history[0]["to_status"] == "VERIFIED"

    # 6. Now verified retailer can publish store listing
    verified_listing = await async_client.post(
        "/api/v1/retailer/listings",
        headers=ret_headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 100000,
            "selling_price_paise": 90000,
            "initial_on_hand_quantity": 10,
        },
    )
    assert verified_listing.status_code == 201
    listing_id = verified_listing.json()["id"]

    # 7. Admin suspends retailer
    suspend_resp = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify",
        headers=admin_headers,
        json={"status": "SUSPENDED", "rejection_reason": "Policy compliance breach"},
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["verification_status"] == "SUSPENDED"
    assert suspend_resp.json()["is_active"] is False

    # 8. Suspended retailer CANNOT create, update, or adjust inventory
    # Create listing attempt
    susp_create = await async_client.post(
        "/api/v1/retailer/listings",
        headers=ret_headers,
        json={
            "variant_id": str(variant_id),
            "original_price_paise": 50000,
            "selling_price_paise": 40000,
            "initial_on_hand_quantity": 5,
        },
    )
    assert susp_create.status_code == 403
    assert susp_create.json()["error"]["code"] in (
        "RETAILER_NOT_VERIFIED",
        "RETAILER_SUSPENDED",
    )

    # Update listing attempt
    susp_update = await async_client.put(
        f"/api/v1/retailer/listings/{listing_id}",
        headers=ret_headers,
        json={"selling_price_paise": 85000},
    )
    assert susp_update.status_code == 403

    # Adjust inventory attempt
    susp_inv = await async_client.post(
        f"/api/v1/retailer/listings/{listing_id}/inventory",
        headers=ret_headers,
        json={"adjustment_type": "DELTA", "quantity": 5},
    )
    assert susp_inv.status_code == 403

    # Cleanup test listing
    async with session_factory() as session:
        await session.execute(
            delete(StoreInventory).where(
                StoreInventory.listing_id == uuid.UUID(listing_id)
            )
        )
        await session.execute(
            delete(ProductListing).where(ProductListing.id == uuid.UUID(listing_id))
        )
        await session.commit()


@pytest.mark.asyncio
async def test_platform_deals_creation_scheduling_and_pricing_integrity(
    async_client: AsyncClient,
):
    """Admin creates platform-wide and category deals; validation protects pricing integrity."""
    admin_headers, _ = await create_user_with_role(async_client, role="admin")

    now = datetime.datetime.now(datetime.UTC)
    future_start = now + datetime.timedelta(days=1)
    future_end = now + datetime.timedelta(days=7)

    # 1. Validation: Percentage discount > 90% rejected
    excessive_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": "Invalid 95% Off Deal",
            "discount_type": "PERCENTAGE",
            "discount_value": 9500,  # 95% > 90%
            "scope": "PLATFORM_WIDE",
        },
    )
    assert excessive_resp.status_code == 422

    # 2. Validation: valid_to <= valid_from rejected
    invalid_dates_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": "Invalid Dates Deal",
            "discount_type": "PERCENTAGE",
            "discount_value": 1000,
            "scope": "PLATFORM_WIDE",
            "valid_from": future_end.isoformat(),
            "valid_to": future_start.isoformat(),
        },
    )
    assert invalid_dates_resp.status_code == 422

    # 3. Create Valid Platform-Wide Percentage Deal (15% off, max ₹300)
    coupon_code = f"FESTIVE{uuid.uuid4().hex[:4].upper()}"
    deal_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": "Festival Mega Sale 15% Off",
            "code": coupon_code,
            "discount_type": "PERCENTAGE",
            "discount_value": 1500,  # 15.00%
            "scope": "PLATFORM_WIDE",
            "max_discount_paise": 30000,  # ₹300 max cap
            "min_order_paise": 50000,  # ₹500 min order
            "valid_from": (now - datetime.timedelta(minutes=5)).isoformat(),
            "valid_to": future_end.isoformat(),
            "description": "Platform-wide festival savings",
        },
    )
    assert deal_resp.status_code == 201
    deal = deal_resp.json()
    deal_id = deal["id"]
    assert deal["code"] == coupon_code
    assert deal["status"] == "ACTIVE"

    # 4. Duplicate coupon code rejected
    dup_code_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": "Another Deal Same Code",
            "code": coupon_code,
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 10000,
            "scope": "PLATFORM_WIDE",
        },
    )
    assert dup_code_resp.status_code == 409
    assert dup_code_resp.json()["error"]["code"] == "COUPON_CODE_ALREADY_EXISTS"

    # 5. Verify DiscountService resolves this deal for a qualifying listing
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Pick any active listing
        listing = (
            (
                await session.execute(
                    select(ProductListing).where(ProductListing.is_active.is_(True))
                )
            )
            .scalars()
            .first()
        )
        assert listing is not None

        discount_service = DiscountService(session)
        # Test item priced at ₹1,000 (100,000 paise) >= ₹500 min order
        applicable = await discount_service.get_applicable_discounts_for_listing(
            listing_id=listing.id,
            selling_price_paise=100000,
        )
        assert any(d.id == uuid.UUID(deal_id) for d in applicable)

        # 15% of ₹1,000 is ₹150 (15,000 paise), which is <= ₹300 cap
        matched_deal = next(d for d in applicable if d.id == uuid.UUID(deal_id))
        total_disc, final_price = DiscountService.calculate_unit_discount(
            100000, [matched_deal]
        )
        assert total_disc == 15000
        assert final_price == 85000

        # Test item priced at ₹4,000 (400,000 paise): 15% is ₹600, capped at ₹300 (30,000 paise)
        capped_disc, capped_price = DiscountService.calculate_unit_discount(
            400000, [matched_deal]
        )
        assert capped_disc == 30000
        assert capped_price == 370000

    # 6. Admin pauses the deal
    pause_resp = await async_client.put(
        f"/api/v1/admin/deals/{deal_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert pause_resp.status_code == 200
    assert pause_resp.json()["status"] == "PAUSED"
    assert pause_resp.json()["is_active"] is False

    # Paused deal no longer applies
    async with session_factory() as session:
        discount_service = DiscountService(session)
        applicable_after_pause = (
            await discount_service.get_applicable_discounts_for_listing(
                listing_id=listing.id,
                selling_price_paise=100000,
            )
        )
        assert all(d.id != uuid.UUID(deal_id) for d in applicable_after_pause)

    # 7. Admin deletes the deal (clean up)
    del_resp = await async_client.delete(
        f"/api/v1/admin/deals/{deal_id}",
        headers=admin_headers,
    )
    assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_scoped_deals_category_and_product_applicability_isolation(
    async_client: AsyncClient,
):
    """Category-specific and Product-specific deals apply strictly to matching items, never leaking."""
    admin_headers, _ = await create_user_with_role(async_client, role="admin")
    session_factory = get_session_factory()

    # 1. Setup two distinct categories
    unique = uuid.uuid4().hex[:6]
    async with session_factory() as session:
        cat_a = Category(
            id=uuid.uuid4(), name=f"Cat A {unique}", slug=f"cat-a-{unique}"
        )
        cat_b = Category(
            id=uuid.uuid4(), name=f"Cat B {unique}", slug=f"cat-b-{unique}"
        )
        session.add_all([cat_a, cat_b])
        await session.flush()

        prod_a = Product(
            id=uuid.uuid4(),
            category_id=cat_a.id,
            name=f"Product A {unique}",
            slug=f"prod-a-{unique}",
            brand="Brand A",
            is_active=False,
        )
        prod_b = Product(
            id=uuid.uuid4(),
            category_id=cat_b.id,
            name=f"Product B {unique}",
            slug=f"prod-b-{unique}",
            brand="Brand B",
            is_active=False,
        )
        session.add_all([prod_a, prod_b])
        await session.flush()

        var_a = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod_a.id,
            name="Variant A",
            sku=f"SKU-A-{unique}",
            is_active=False,
        )
        var_b = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod_b.id,
            name="Variant B",
            sku=f"SKU-B-{unique}",
            is_active=False,
        )
        session.add_all([var_a, var_b])
        await session.flush()

        # Any retailer to own listings
        ret = (await session.execute(select(Retailer).limit(1))).scalars().first()
        listing_a = ProductListing(
            id=uuid.uuid4(),
            retailer_id=ret.id,
            variant_id=var_a.id,
            original_price_paise=50000,
            selling_price_paise=45000,
            currency="INR",
            is_active=False,
        )
        listing_b = ProductListing(
            id=uuid.uuid4(),
            retailer_id=ret.id,
            variant_id=var_b.id,
            original_price_paise=50000,
            selling_price_paise=45000,
            currency="INR",
            is_active=False,
        )
        session.add_all([listing_a, listing_b])
        await session.commit()

        cat_a_id = cat_a.id
        cat_b_id = cat_b.id
        prod_a_id = prod_a.id
        prod_b_id = prod_b.id
        var_a_id = var_a.id
        var_b_id = var_b.id
        listing_a_id = listing_a.id
        listing_b_id = listing_b.id

    # 2. Admin creates Category Deal for Category A only (₹100 off, fixed)
    cat_deal_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": f"Cat A ₹100 Off {unique}",
            "discount_type": "FIXED_AMOUNT",
            "discount_value": 10000,
            "scope": "CATEGORY",
            "category_id": str(cat_a_id),
        },
    )
    assert cat_deal_resp.status_code == 201
    cat_deal_id = cat_deal_resp.json()["id"]

    # 3. Admin creates Product Deal for Product B only (10% off) with usage_limit = 1
    prod_deal_resp = await async_client.post(
        "/api/v1/admin/deals",
        headers=admin_headers,
        json={
            "name": f"Prod B 10% Off {unique}",
            "discount_type": "PERCENTAGE",
            "discount_value": 1000,
            "scope": "PRODUCT",
            "product_id": str(prod_b_id),
            "usage_limit": 1,
        },
    )
    assert prod_deal_resp.status_code == 201
    prod_deal_id = prod_deal_resp.json()["id"]

    # 4. Verify discount service applies correctly per scope
    async with session_factory() as session:
        discount_service = DiscountService(session)

        # Listing A (belongs to Cat A): MUST receive Category Deal, MUST NOT receive Product B deal
        discounts_a = await discount_service.get_applicable_discounts_for_listing(
            listing_id=listing_a_id,
            selling_price_paise=45000,
        )
        assert any(d.id == uuid.UUID(cat_deal_id) for d in discounts_a)
        assert all(d.id != uuid.UUID(prod_deal_id) for d in discounts_a)

        # Listing B (belongs to Cat B & Prod B): MUST receive Product B deal, MUST NOT receive Category A deal
        discounts_b = await discount_service.get_applicable_discounts_for_listing(
            listing_id=listing_b_id,
            selling_price_paise=45000,
        )
        assert any(d.id == uuid.UUID(prod_deal_id) for d in discounts_b)
        assert all(d.id != uuid.UUID(cat_deal_id) for d in discounts_b)

        # 5. Usage Limit Enforcement: Simulate times_used reaching usage_limit (1)
        from app.modules.pricing.models import Discount

        await session.execute(
            update(Discount)
            .where(Discount.id == uuid.UUID(prod_deal_id))
            .values(times_used=1)
        )
        await session.commit()

        # Listing B should no longer receive Product B deal because usage limit is reached
        discounts_b_after_limit = (
            await discount_service.get_applicable_discounts_for_listing(
                listing_id=listing_b_id,
                selling_price_paise=45000,
            )
        )
        assert all(d.id != uuid.UUID(prod_deal_id) for d in discounts_b_after_limit)

    # 6. Clean up test deals
    await async_client.delete(
        f"/api/v1/admin/deals/{cat_deal_id}", headers=admin_headers
    )
    await async_client.delete(
        f"/api/v1/admin/deals/{prod_deal_id}", headers=admin_headers
    )

    # 7. Clean up scoped test products, variants, listings, and categories
    async with session_factory() as session:
        await session.execute(
            delete(ProductListing).where(
                ProductListing.id.in_([listing_a_id, listing_b_id])
            )
        )
        await session.execute(
            delete(ProductVariant).where(ProductVariant.id.in_([var_a_id, var_b_id]))
        )
        await session.execute(
            delete(Product).where(Product.id.in_([prod_a_id, prod_b_id]))
        )
        await session.execute(
            delete(Category).where(Category.id.in_([cat_a_id, cat_b_id]))
        )
        await session.commit()
