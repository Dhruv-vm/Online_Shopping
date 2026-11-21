import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.database import get_session_factory
from app.modules.catalogue.models import ProductListing, Retailer
from app.modules.pricing.models import CheckoutQuote
from tests.factories import create_test_listing, get_test_listing


@pytest.mark.asyncio
async def test_quote_generation_guest(async_client: AsyncClient):
    # 1. Guest adds item to cart
    listing = await get_test_listing(async_client)
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert add_resp.status_code == 200
    assert "basket_guest_cart" in add_resp.cookies

    # 2. Generate quote
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={},
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()

    assert quote["status"] == "ACTIVE"
    assert quote["is_consumed"] is False
    assert len(quote["items"]) == 1
    item = quote["items"][0]
    assert item["listing_id"] == listing["id"]
    assert item["quantity"] == 1
    assert item["unit_selling_price_paise"] == listing["selling_price_paise"]
    assert item["total_selling_price_paise"] == listing["selling_price_paise"]

    # Tax reconciliation: taxable base + total tax == selling price
    assert (
        item["taxable_base_paise"] + item["total_tax_paise"]
        == item["total_selling_price_paise"]
    )
    assert (
        item["cgst_paise"] + item["sgst_paise"] + item["igst_paise"]
        == item["total_tax_paise"]
    )

    # Expiry is set 15 minutes in future
    expires_at = datetime.fromisoformat(quote["expires_at"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert expires_at > now
    assert expires_at <= now + timedelta(minutes=16)

    # 3. Retrieve quote by ID
    get_resp = await async_client.get(f"/api/v1/quotes/{quote['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == quote["id"]


@pytest.mark.asyncio
async def test_quote_generation_authenticated_with_intra_state_gst(
    async_client: AsyncClient,
):
    # 1. Register customer
    email = f"quote_intra_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Intra Tester",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Create Address in Karnataka (KA)
    addr_resp = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Intra Tester",
            "phone": "+919876543210",
            "line1": "100 MG Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
            "is_default": True,
        },
        headers=auth_header,
    )
    assert addr_resp.status_code == 201
    address_id = addr_resp.json()["id"]

    # 3. Add item from Croma (KA retailer) to cart
    listing = await create_test_listing(
        retailer_name="Croma KA",
        retailer_state="KA",
        gst_rate_basis_points=1800,
    )
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
        headers=auth_header,
    )
    assert add_resp.status_code == 200

    # 4. Generate quote specifying delivery_address_id
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={"delivery_address_id": address_id},
        headers=auth_header,
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    assert quote["customer_id"] is not None
    assert quote["delivery_address_id"] == address_id

    # For any item where retailer is KA and delivery is KA, CGST and SGST must apply
    for it in quote["items"]:
        if it["retailer_state"] == "KA":
            assert it["cgst_paise"] > 0
            assert it["sgst_paise"] > 0
            assert it["igst_paise"] == 0


@pytest.mark.asyncio
async def test_quote_generation_inter_state_gst(async_client: AsyncClient):
    # 1. Register customer
    email = f"quote_inter_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Inter Tester",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Create Address in Delhi (DL)
    addr_resp = await async_client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Inter Tester",
            "phone": "+919876543210",
            "line1": "Connaught Place",
            "city": "New Delhi",
            "state": "Delhi",
            "postal_code": "110001",
            "is_default": True,
        },
        headers=auth_header,
    )
    assert addr_resp.status_code == 201
    address_id = addr_resp.json()["id"]

    # 3. Add item from Croma (KA retailer) to cart
    listing = await create_test_listing(
        retailer_name="Croma KA",
        retailer_state="KA",
        gst_rate_basis_points=1800,
    )
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
        headers=auth_header,
    )

    # 4. Generate quote specifying Delhi address
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={"delivery_address_id": address_id},
        headers=auth_header,
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()

    # For item where retailer is KA and delivery is DL (inter-state): IGST applies
    for it in quote["items"]:
        if it["retailer_state"] != "DL":
            assert it["cgst_paise"] == 0
            assert it["sgst_paise"] == 0
            assert it["igst_paise"] > 0
            assert it["igst_paise"] == it["total_tax_paise"]


@pytest.mark.asyncio
async def test_quote_customer_isolation(async_client: AsyncClient):
    # Customer A registers and creates a quote
    email_a = f"cust_a_{uuid.uuid4().hex[:8]}@example.com"
    reg_a = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email_a,
            "password": "Password123!",
            "full_name": "Cust A",
            "phone": "+919876543210",
        },
    )
    token_a = reg_a.json()["access_token"]
    auth_a = {"Authorization": f"Bearer {token_a}"}

    listing = await get_test_listing(async_client)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
        headers=auth_a,
    )
    quote_a_resp = await async_client.post(
        "/api/v1/quotes",
        json={},
        headers=auth_a,
    )
    quote_a_id = quote_a_resp.json()["id"]

    # Customer B registers
    email_b = f"cust_b_{uuid.uuid4().hex[:8]}@example.com"
    reg_b = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email_b,
            "password": "Password123!",
            "full_name": "Cust B",
            "phone": "+919876543210",
        },
    )
    token_b = reg_b.json()["access_token"]
    auth_b = {"Authorization": f"Bearer {token_b}"}

    # Customer B attempts to access Customer A's quote -> 404 Not Found
    forbidden_resp = await async_client.get(
        f"/api/v1/quotes/{quote_a_id}",
        headers=auth_b,
    )
    assert forbidden_resp.status_code == 404
    assert forbidden_resp.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_quote_immutability_and_repricing_detection(async_client: AsyncClient):
    listing = await get_test_listing(async_client)
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert add_resp.status_code == 200

    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={},
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    quote_id = quote["id"]
    original_price = quote["items"][0]["unit_selling_price_paise"]

    # 1. Validation before price change passes
    val_resp1 = await async_client.post(f"/api/v1/quotes/{quote_id}/validate")
    assert val_resp1.status_code == 200
    assert val_resp1.json()["valid"] is True

    # 2. Mutate listing selling price in DB
    session_factory = get_session_factory()
    new_price = original_price + 50000  # +₹500
    async with session_factory() as session:
        await session.execute(
            update(ProductListing)
            .where(ProductListing.id == uuid.UUID(listing["id"]))
            .values(selling_price_paise=new_price)
        )
        await session.commit()

    try:
        # 3. Existing quote preserves original immutable price snapshot
        fetched_quote = await async_client.get(f"/api/v1/quotes/{quote_id}")
        assert fetched_quote.status_code == 200
        assert (
            fetched_quote.json()["items"][0]["unit_selling_price_paise"]
            == original_price
        )

        # 4. Validation detects the price discrepancy
        val_resp2 = await async_client.post(f"/api/v1/quotes/{quote_id}/validate")
        assert val_resp2.status_code == 200
        val_data = val_resp2.json()
        assert val_data["valid"] is False
        assert val_data["reason"] == "PRICE_CHANGED"
        assert val_data["can_refresh"] is True

        # 5. Refresh quote generates replacement and marks old quote SUPERSEDED
        refresh_resp = await async_client.post(f"/api/v1/quotes/{quote_id}/refresh")
        assert refresh_resp.status_code == 201
        new_quote = refresh_resp.json()
        assert new_quote["id"] != quote_id
        assert new_quote["items"][0]["unit_selling_price_paise"] == new_price

        # Check old quote is SUPERSEDED
        old_check = await async_client.get(f"/api/v1/quotes/{quote_id}")
        assert old_check.status_code == 200
        assert old_check.json()["status"] == "SUPERSEDED"
        assert old_check.json()["superseded_by_quote_id"] == new_quote["id"]
    finally:
        # Restore listing price
        async with session_factory() as session:
            await session.execute(
                update(ProductListing)
                .where(ProductListing.id == uuid.UUID(listing["id"]))
                .values(selling_price_paise=original_price)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_quote_expiry_detection(async_client: AsyncClient):
    listing = await get_test_listing(async_client)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )

    quote_resp = await async_client.post("/api/v1/quotes", json={})
    assert quote_resp.status_code == 201
    quote_id = quote_resp.json()["id"]

    # Artificially expire the quote in DB
    session_factory = get_session_factory()
    past_time = datetime.now(UTC) - timedelta(minutes=5)
    async with session_factory() as session:
        await session.execute(
            update(CheckoutQuote)
            .where(CheckoutQuote.id == uuid.UUID(quote_id))
            .values(expires_at=past_time)
        )
        await session.commit()

    # Validation detects expiry
    val_resp = await async_client.post(f"/api/v1/quotes/{quote_id}/validate")
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is False
    assert val_data["reason"] == "EXPIRED"

    # Status updated to EXPIRED
    get_resp = await async_client.get(f"/api/v1/quotes/{quote_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_empty_cart_quote_rejected(async_client: AsyncClient):
    # Fresh client with empty cart
    async_client.cookies.clear()
    resp = await async_client.post("/api/v1/quotes", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_CART"


@pytest.mark.asyncio
async def test_guest_quote_security_isolation_between_guests(async_client: AsyncClient):
    # 1. Guest A creates a cart and quote
    async_client.cookies.clear()
    listing = await get_test_listing(async_client)
    add_a = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert add_a.status_code == 200
    cookie_a = async_client.cookies.get("basket_guest_cart")
    assert cookie_a is not None

    quote_a = (await async_client.post("/api/v1/quotes", json={})).json()
    quote_a_id = quote_a["id"]

    # 2. Switch to Guest B (clear and issue new guest cookie)
    async_client.cookies.clear()
    add_b = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    assert add_b.status_code == 200
    cookie_b = async_client.cookies.get("basket_guest_cart")
    assert cookie_b != cookie_a

    # Guest B attempts to fetch Guest A's quote -> 404 QUOTE_NOT_FOUND
    forbidden_get = await async_client.get(f"/api/v1/quotes/{quote_a_id}")
    assert forbidden_get.status_code == 404
    assert forbidden_get.json()["error"]["code"] == "QUOTE_NOT_FOUND"

    # Guest B attempts to validate Guest A's quote -> 404 QUOTE_NOT_FOUND
    forbidden_val = await async_client.post(f"/api/v1/quotes/{quote_a_id}/validate")
    assert forbidden_val.status_code == 404
    assert forbidden_val.json()["error"]["code"] == "QUOTE_NOT_FOUND"

    # Guest B attempts to refresh Guest A's quote -> 404 QUOTE_NOT_FOUND
    forbidden_ref = await async_client.post(f"/api/v1/quotes/{quote_a_id}/refresh")
    assert forbidden_ref.status_code == 404
    assert forbidden_ref.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_unauthenticated_caller_without_cookies_cannot_access_quotes(
    async_client: AsyncClient,
):
    # 1. Guest creates quote
    listing = await get_test_listing(async_client)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    quote = (await async_client.post("/api/v1/quotes", json={})).json()
    quote_id = quote["id"]

    # 2. Caller strips all cookies and headers
    async_client.cookies.clear()
    resp = await async_client.get(f"/api/v1/quotes/{quote_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_authenticated_customer_cannot_access_guest_quote(
    async_client: AsyncClient,
):
    # 1. Guest creates quote
    async_client.cookies.clear()
    listing = await get_test_listing(async_client)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    quote = (await async_client.post("/api/v1/quotes", json={})).json()
    quote_id = quote["id"]

    # 2. Register separate authenticated customer
    async_client.cookies.clear()
    email = f"auth_isolate_{uuid.uuid4().hex[:8]}@example.com"
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Isolate Tester",
            "phone": "+919876543210",
        },
    )
    token = reg.json()["access_token"]

    # Customer attempts to fetch guest quote -> 404
    resp = await async_client.get(
        f"/api/v1/quotes/{quote_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "QUOTE_NOT_FOUND"


@pytest.mark.asyncio
async def test_missing_or_invalid_tax_classification_fails_quote_generation(
    async_client: AsyncClient,
):
    listing = await get_test_listing(async_client)
    listing_uuid = uuid.UUID(listing["id"])
    orig_hsn = listing.get("hsn_code", "8518")
    orig_gst = listing.get("gst_rate_basis_points", 1800)

    session_factory = get_session_factory()

    # Clear listing HSN code in database
    async with session_factory() as session:
        await session.execute(
            update(ProductListing)
            .where(ProductListing.id == listing_uuid)
            .values(hsn_code=None)
        )
        await session.commit()

    try:
        async_client.cookies.clear()
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": listing["id"], "quantity": 1},
        )
        fail_resp = await async_client.post("/api/v1/quotes", json={})
        assert fail_resp.status_code == 422
        assert fail_resp.json()["error"]["code"] == "INVALID_TAX_CLASSIFICATION"
    finally:
        # Restore valid classification
        async with session_factory() as session:
            await session.execute(
                update(ProductListing)
                .where(ProductListing.id == listing_uuid)
                .values(hsn_code=orig_hsn, gst_rate_basis_points=orig_gst)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_invalid_delivery_state_fails_quote_generation(
    async_client: AsyncClient,
):
    listing = await get_test_listing(async_client)
    async_client.cookies.clear()
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )

    # Invalid state "XX_NON_EXISTENT"
    fail_resp = await async_client.post(
        "/api/v1/quotes",
        json={"delivery_state": "XX_NON_EXISTENT"},
    )
    assert fail_resp.status_code == 422
    assert fail_resp.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.asyncio
async def test_missing_or_invalid_retailer_state_fails_quote_generation(
    async_client: AsyncClient,
):
    listing = await get_test_listing(async_client)
    retailer_id = uuid.UUID(listing["retailer_id"])
    session_factory = get_session_factory()

    # Set retailer state to invalid in DB
    async with session_factory() as session:
        await session.execute(
            update(Retailer).where(Retailer.id == retailer_id).values(state=None)
        )
        await session.commit()

    try:
        async_client.cookies.clear()
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": listing["id"], "quantity": 1},
        )
        fail_resp = await async_client.post("/api/v1/quotes", json={})
        assert fail_resp.status_code == 422
        assert fail_resp.json()["error"]["code"] == "MISSING_STATE"
    finally:
        # Restore retailer state
        async with session_factory() as session:
            await session.execute(
                update(Retailer).where(Retailer.id == retailer_id).values(state="KA")
            )
            await session.commit()
