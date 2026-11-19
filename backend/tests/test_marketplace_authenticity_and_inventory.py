import datetime
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.database import get_session_factory
from app.modules.catalogue.models import (
    Category,
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
    StoreInventory,
)
from app.modules.identity.models import User
from app.modules.inventory.models import (
    InventoryReservation,
    InventoryReservationItem,
    ReservationStatus,
)
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.pricing.models import CheckoutQuote, QuoteStatus


async def create_user_with_role(
    async_client: AsyncClient,
    role: str = "customer",
    suffix: str = "",
) -> tuple[dict[str, str], dict]:
    """Helper to register a user with a specific role and return auth header and user dict."""
    unique = uuid.uuid4().hex[:8] + suffix
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
async def test_storefront_excludes_unverified_and_inactive_retailers(
    async_client: AsyncClient,
):
    """Customer storefront only lists products and offers from VERIFIED, active retailers."""
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    async with session_factory() as session:
        # 1. Create a Category
        cat = Category(
            id=uuid.uuid4(),
            name=f"Authenticity Cat {unique}",
            slug=f"auth-cat-{unique}",
            is_active=True,
        )
        session.add(cat)

        # 2. Create a Product and Variant
        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=f"Authentic Product {unique}",
            brand="Basket Brand",
            slug=f"auth-prod-{unique}",
            is_active=True,
        )
        session.add(prod)

        variant = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            sku=f"AUTH-SKU-{unique}",
            name="Default Variant",
            attributes={},
            is_active=True,
        )
        session.add(variant)

        # 3. Create Verified Retailer
        ret_verified = Retailer(
            id=uuid.uuid4(),
            name=f"Verified Store {unique}",
            slug=f"verified-store-{unique}",
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        session.add(ret_verified)

        # 4. Create Unverified Retailer
        ret_unverified = Retailer(
            id=uuid.uuid4(),
            name=f"Pending Store {unique}",
            slug=f"pending-store-{unique}",
            state="MH",
            is_active=True,
            verification_status="PENDING",
        )
        session.add(ret_unverified)

        # 5. Create Inactive Retailer
        ret_inactive = Retailer(
            id=uuid.uuid4(),
            name=f"Inactive Store {unique}",
            slug=f"inactive-store-{unique}",
            state="DL",
            is_active=False,
            verification_status="VERIFIED",
        )
        session.add(ret_inactive)

        await session.flush()

        # Listings for each retailer
        listing_v = ProductListing(
            id=uuid.uuid4(),
            variant_id=variant.id,
            retailer_id=ret_verified.id,
            selling_price_paise=85000,
            original_price_paise=100000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        listing_u = ProductListing(
            id=uuid.uuid4(),
            variant_id=variant.id,
            retailer_id=ret_unverified.id,
            selling_price_paise=80000,
            original_price_paise=100000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        listing_i = ProductListing(
            id=uuid.uuid4(),
            variant_id=variant.id,
            retailer_id=ret_inactive.id,
            selling_price_paise=75000,
            original_price_paise=100000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        session.add_all([listing_v, listing_u, listing_i])
        await session.flush()

        # Store inventories with stock
        inv_v = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_v.id,
            on_hand_quantity=10,
            reserved_quantity=0,
        )
        inv_u = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_u.id,
            on_hand_quantity=10,
            reserved_quantity=0,
        )
        inv_i = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_i.id,
            on_hand_quantity=10,
            reserved_quantity=0,
        )
        session.add_all([inv_v, inv_u, inv_i])
        await session.commit()

    # Query product detail through public customer endpoint
    detail_resp = await async_client.get(f"/api/v1/products/{prod.id}")
    assert detail_resp.status_code == 200
    pdata = detail_resp.json()

    # Verify only the verified retailer's listing is present under variants
    listings = pdata["variants"][0]["listings"]
    active_retailers = [item["retailer_name"] for item in listings]
    assert f"Verified Store {unique}" in active_retailers
    assert f"Pending Store {unique}" not in active_retailers
    assert f"Inactive Store {unique}" not in active_retailers
    assert len(listings) == 1


@pytest.mark.asyncio
async def test_storefront_multi_seller_offer_selection(async_client: AsyncClient):
    """Customer PDP presents multi-seller offers with distinct prices, states, and stock."""
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Laptop Cat {unique}",
            slug=f"laptop-cat-{unique}",
            is_active=True,
        )
        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=f"Flagship Laptop {unique}",
            brand="TechCorp",
            slug=f"flagship-laptop-{unique}",
            is_active=True,
        )
        session.add_all([cat, prod])

        variant = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            sku=f"LAPTOP-SKU-{unique}",
            name="16GB / 512GB SSD",
            attributes={"ram": "16GB", "storage": "512GB"},
            is_active=True,
        )
        session.add(variant)

        ret_a = Retailer(
            id=uuid.uuid4(),
            name=f"Retailer Alpha {unique}",
            slug=f"retailer-alpha-{unique}",
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        ret_b = Retailer(
            id=uuid.uuid4(),
            name=f"Retailer Beta {unique}",
            slug=f"retailer-beta-{unique}",
            state="MH",
            is_active=True,
            verification_status="VERIFIED",
        )
        session.add_all([ret_a, ret_b])
        await session.flush()

        listing_a = ProductListing(
            id=uuid.uuid4(),
            variant_id=variant.id,
            retailer_id=ret_a.id,
            selling_price_paise=12490000,
            original_price_paise=13490000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        listing_b = ProductListing(
            id=uuid.uuid4(),
            variant_id=variant.id,
            retailer_id=ret_b.id,
            selling_price_paise=12749000,
            original_price_paise=13490000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        session.add_all([listing_a, listing_b])
        await session.flush()

        inv_a = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_a.id,
            on_hand_quantity=15,
            reserved_quantity=0,
        )
        inv_b = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_b.id,
            on_hand_quantity=8,
            reserved_quantity=0,
        )
        session.add_all([inv_a, inv_b])
        await session.commit()

    detail_resp = await async_client.get(f"/api/v1/products/{prod.id}")
    assert detail_resp.status_code == 200
    pdata = detail_resp.json()

    listings = pdata["variants"][0]["listings"]
    assert len(listings) == 2
    prices = {item["retailer_name"]: item["selling_price_paise"] for item in listings}
    assert prices[f"Retailer Alpha {unique}"] == 12490000
    assert prices[f"Retailer Beta {unique}"] == 12749000

    states = {item["retailer_name"]: item.get("retailer_state") for item in listings}
    assert states[f"Retailer Alpha {unique}"] == "KA"
    assert states[f"Retailer Beta {unique}"] == "MH"


@pytest.mark.asyncio
async def test_inventory_atomic_deduction_and_idempotency():
    """Permanent stock deduction occurs on confirmation and repeated confirmation is idempotent."""
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    listing_id = uuid.uuid4()
    retailer_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    quote_id = uuid.uuid4()
    res_id = uuid.uuid4()

    async with session_factory() as session:
        # Create prerequisite retailer, category, product, variant, listing
        cat = Category(
            id=uuid.uuid4(),
            name=f"Inv Cat {unique}",
            slug=f"inv-cat-{unique}",
            is_active=True,
        )
        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=f"Inv Product {unique}",
            brand="StockBrand",
            slug=f"inv-prod-{unique}",
            is_active=True,
        )
        var = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            sku=f"INV-SKU-{unique}",
            name="StockVariant",
            attributes={},
            is_active=True,
        )
        ret = Retailer(
            id=retailer_id,
            name=f"Stock Retailer {unique}",
            slug=f"stock-ret-{unique}",
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        listing = ProductListing(
            id=listing_id,
            variant_id=var.id,
            retailer_id=retailer_id,
            selling_price_paise=10000,
            original_price_paise=15000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        inv = StoreInventory(
            id=inv_id,
            listing_id=listing_id,
            on_hand_quantity=20,
            reserved_quantity=3,  # 3 units currently reserved
        )
        quote = CheckoutQuote(
            id=quote_id,
            guest_token_hash="a" * 64,
            subtotal_paise=30000,
            total_payable_paise=30000,
            status=QuoteStatus.ACTIVE.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=15),
        )
        res = InventoryReservation(
            id=res_id,
            guest_token_hash="a" * 64,
            quote_id=quote_id,
            status=ReservationStatus.ACTIVE.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=10),
        )
        res_item = InventoryReservationItem(
            id=uuid.uuid4(),
            reservation_id=res_id,
            listing_id=listing_id,
            retailer_id=retailer_id,
            variant_id=var.id,
            quantity=3,
        )
        session.add_all([cat, prod, var, ret, listing, inv, quote, res, res_item])
        await session.commit()

    # 1. First confirmation: should deduct on_hand and clear reserved
    async with session_factory() as session:
        service = ReservationService(session)
        confirmed_res = await service.confirm_reservation(
            reservation_id=res_id,
            internal=True,
        )
        await session.commit()
        assert confirmed_res.status == ReservationStatus.CONFIRMED.value

    # Verify inventory state: on_hand=17, reserved=0
    async with session_factory() as session:
        check_inv = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.id == inv_id)
            )
        ).scalar_one()
        assert check_inv.on_hand_quantity == 17
        assert check_inv.reserved_quantity == 0

    # 2. Second confirmation (idempotent replay): must NOT deduct stock again
    async with session_factory() as session:
        service = ReservationService(session)
        replayed_res = await service.confirm_reservation(
            reservation_id=res_id,
            internal=True,
        )
        await session.commit()
        assert replayed_res.status == ReservationStatus.CONFIRMED.value

    # Verify inventory state is completely unchanged
    async with session_factory() as session:
        check_inv2 = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.id == inv_id)
            )
        ).scalar_one()
        assert check_inv2.on_hand_quantity == 17
        assert check_inv2.reserved_quantity == 0


@pytest.mark.asyncio
async def test_admin_retailer_directory_search_and_filters(async_client: AsyncClient):
    """Admin can search and filter retailers by name and registered state."""
    admin_headers, _ = await create_user_with_role(
        async_client, role="admin", suffix="_dir"
    )
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    # Seed isolated test retailers to ensure test is fully hermetic even on a fresh DB
    r_ka_id = uuid.uuid4()
    r_mh_id = uuid.uuid4()
    ka_keyword = f"KrnStore{unique}"
    async with session_factory() as session:
        r_ka = Retailer(
            id=r_ka_id,
            name=f"Bengaluru {ka_keyword}",
            slug=f"bengaluru-{ka_keyword.lower()}",
            state="KA",
            business_address=f"100 MG Road, Bengaluru {unique}",
            is_active=True,
            verification_status="VERIFIED",
        )
        r_mh = Retailer(
            id=r_mh_id,
            name=f"Mumbai Mega Store {unique}",
            slug=f"mumbai-mega-store-{unique}",
            state="MH",
            business_address=f"200 Bandra, Mumbai {unique}",
            is_active=True,
            verification_status="VERIFIED",
        )
        session.add_all([r_ka, r_mh])
        await session.commit()

    # Filter by state KA
    resp_ka = await async_client.get(
        "/api/v1/admin/retailers?state=KA&limit=50",
        headers=admin_headers,
    )
    assert resp_ka.status_code == 200
    data_ka = resp_ka.json()
    assert isinstance(data_ka, list)
    assert len(data_ka) > 0
    returned_ids_ka = [r["id"] for r in data_ka]
    assert str(r_ka_id) in returned_ids_ka
    assert str(r_mh_id) not in returned_ids_ka
    for r in data_ka:
        assert r["state"] == "KA"

    # Search by store name
    resp_search = await async_client.get(
        f"/api/v1/admin/retailers?search={ka_keyword}&limit=20",
        headers=admin_headers,
    )
    assert resp_search.status_code == 200
    data_search = resp_search.json()
    assert isinstance(data_search, list)
    assert len(data_search) > 0
    returned_ids_search = [r["id"] for r in data_search]
    assert str(r_ka_id) in returned_ids_search
    assert str(r_mh_id) not in returned_ids_search
    for r in data_search:
        assert (
            "bengaluru" in r["name"].lower()
            or "bengaluru" in (r.get("business_address") or "").lower()
            or ka_keyword.lower() in r["name"].lower()
        )


@pytest.mark.asyncio
async def test_admin_retailer_sales_analytics_and_rbac(async_client: AsyncClient):
    """Admin can view store-wise sales analytics; non-admins are strictly forbidden."""
    admin_headers, _ = await create_user_with_role(
        async_client, role="admin", suffix="_analyt"
    )
    cust_headers, cust_user = await create_user_with_role(
        async_client, role="customer", suffix="_analyt"
    )
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    ret_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    var_id = uuid.uuid4()
    order_id = uuid.uuid4()
    listing_id = uuid.uuid4()
    quote_id = uuid.uuid4()
    res_id = uuid.uuid4()

    async with session_factory() as session:
        # Create Retailer
        retailer = Retailer(
            id=ret_id,
            name=f"Analytics Test Store {unique}",
            slug=f"analytics-store-{unique}",
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        session.add(retailer)

        cat = Category(
            id=uuid.uuid4(),
            name=f"Analytics Cat {unique}",
            slug=f"analyt-cat-{unique}",
            is_active=True,
        )
        prod = Product(
            id=prod_id,
            category_id=cat.id,
            name=f"Analytics Product {unique}",
            brand="DataBrand",
            slug=f"analyt-prod-{unique}",
            is_active=True,
        )
        var = ProductVariant(
            id=var_id,
            product_id=prod_id,
            sku=f"ANALYT-SKU-{unique}",
            name="Standard",
            attributes={},
            is_active=True,
        )
        listing = ProductListing(
            id=listing_id,
            variant_id=var_id,
            retailer_id=ret_id,
            selling_price_paise=45000,
            original_price_paise=50000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        inv = StoreInventory(
            id=uuid.uuid4(),
            listing_id=listing_id,
            on_hand_quantity=50,
            reserved_quantity=0,
        )
        quote = CheckoutQuote(
            id=quote_id,
            customer_id=uuid.UUID(cust_user["id"]),
            subtotal_paise=90000,
            total_payable_paise=90000,
            status=QuoteStatus.ACTIVE.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=15),
        )
        res = InventoryReservation(
            id=res_id,
            customer_id=uuid.UUID(cust_user["id"]),
            quote_id=quote_id,
            status=ReservationStatus.CONFIRMED.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=10),
        )
        session.add_all([cat, prod, var, listing, inv, quote, res])
        await session.flush()

        # Create confirmed order with order items
        order = Order(
            id=order_id,
            order_number=f"ORD-ANALYT-{unique}",
            quote_id=quote_id,
            reservation_id=res_id,
            customer_id=uuid.UUID(cust_user["id"]),
            delivery_address_snapshot={
                "full_name": "Test Customer",
                "phone": "9876543211",
                "address_line1": "123 Indiranagar",
                "city": "Bengaluru",
                "state": "KA",
                "postal_code": "560038",
            },
            subtotal_paise=90000,
            total_payable_paise=90000,
            status=OrderStatus.CONFIRMED.value,
            payment_status="SUCCEEDED",
            payment_window_expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(hours=1),
        )
        session.add(order)
        await session.flush()

        order_item = OrderItem(
            id=uuid.uuid4(),
            order_id=order_id,
            listing_id=listing_id,
            variant_id=var_id,
            retailer_id=ret_id,
            product_title=f"Analytics Product {unique}",
            variant_title="Standard",
            sku=f"ANALYT-SKU-{unique}",
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            quantity=2,
            unit_original_price_paise=45000,
            unit_selling_price_paise=45000,
            unit_discount_paise=0,
            unit_discounted_price_paise=45000,
            total_selling_price_paise=90000,
            taxable_base_paise=76271,
            cgst_paise=6864,
            sgst_paise=6864,
            igst_paise=0,
            total_tax_paise=13729,
            retailer_name=retailer.name,
            retailer_state="KA",
        )
        session.add(order_item)
        await session.commit()

    # 1. Non-admin customer access must be rejected with 403 Forbidden
    cust_resp = await async_client.get(
        f"/api/v1/admin/retailers/{ret_id}/analytics",
        headers=cust_headers,
    )
    assert cust_resp.status_code == 403

    # 2. Admin access succeeds with accurate computed analytics
    admin_resp = await async_client.get(
        f"/api/v1/admin/retailers/{ret_id}/analytics",
        headers=admin_headers,
    )
    assert admin_resp.status_code == 200
    adata = admin_resp.json()

    assert adata["retailer_id"] == str(ret_id)
    assert adata["retailer_name"] == f"Analytics Test Store {unique}"
    assert adata["total_orders"] == 1
    assert adata["total_units_sold"] == 2
    assert adata["gross_merchandise_value_paise"] == 90000
    assert adata["refunded_amount_paise"] == 0
    assert adata["net_sales_paise"] == 90000
    assert len(adata["product_sales"]) == 1
    ps = adata["product_sales"][0]
    assert ps["product_name"] == f"Analytics Product {unique}"
    assert ps["quantity_sold"] == 2
    assert ps["gross_revenue_paise"] == 90000
    assert ps["net_sales_paise"] == 90000


@pytest.mark.asyncio
async def test_inventory_release_restores_reserved_stock():
    """Released or cancelled reservation restores reserved quantity without affecting on-hand stock."""
    session_factory = get_session_factory()
    unique = uuid.uuid4().hex[:6]

    listing_id = uuid.uuid4()
    retailer_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    quote_id = uuid.uuid4()
    res_id = uuid.uuid4()

    async with session_factory() as session:
        cat = Category(
            id=uuid.uuid4(),
            name=f"Rel Cat {unique}",
            slug=f"rel-cat-{unique}",
            is_active=True,
        )
        prod = Product(
            id=uuid.uuid4(),
            category_id=cat.id,
            name=f"Rel Product {unique}",
            brand="RelBrand",
            slug=f"rel-prod-{unique}",
            is_active=True,
        )
        var = ProductVariant(
            id=uuid.uuid4(),
            product_id=prod.id,
            sku=f"REL-SKU-{unique}",
            name="RelVariant",
            attributes={},
            is_active=True,
        )
        ret = Retailer(
            id=retailer_id,
            name=f"Rel Retailer {unique}",
            slug=f"rel-ret-{unique}",
            state="KA",
            is_active=True,
            verification_status="VERIFIED",
        )
        listing = ProductListing(
            id=listing_id,
            variant_id=var.id,
            retailer_id=retailer_id,
            selling_price_paise=10000,
            original_price_paise=15000,
            hsn_code="84713010",
            gst_rate_basis_points=1800,
            is_tax_verified=True,
            is_active=True,
        )
        inv = StoreInventory(
            id=inv_id,
            listing_id=listing_id,
            on_hand_quantity=25,
            reserved_quantity=5,
        )
        quote = CheckoutQuote(
            id=quote_id,
            guest_token_hash="b" * 64,
            subtotal_paise=50000,
            total_payable_paise=50000,
            status=QuoteStatus.ACTIVE.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=15),
        )
        res = InventoryReservation(
            id=res_id,
            guest_token_hash="b" * 64,
            quote_id=quote_id,
            status=ReservationStatus.ACTIVE.value,
            expires_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=10),
        )
        res_item = InventoryReservationItem(
            id=uuid.uuid4(),
            reservation_id=res_id,
            listing_id=listing_id,
            retailer_id=retailer_id,
            variant_id=var.id,
            quantity=5,
        )
        session.add_all([cat, prod, var, ret, listing, inv, quote, res, res_item])
        await session.commit()

    # Release the reservation
    async with session_factory() as session:
        service = ReservationService(session)
        released = await service.release_reservation(
            reservation_id=res_id,
            guest_token_hash="b" * 64,
            reason="EXPIRED_CHECKOUT_TIMEOUT",
        )
        await session.commit()
        assert released.status == ReservationStatus.RELEASED.value

    # Verify inventory: reserved_quantity reset to 0, on_hand remains 25
    async with session_factory() as session:
        check_inv = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.id == inv_id)
            )
        ).scalar_one()
        assert check_inv.on_hand_quantity == 25
        assert check_inv.reserved_quantity == 0
