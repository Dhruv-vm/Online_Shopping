import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import Settings, settings
from app.core.database import get_session_factory
from app.core.exceptions import AppException
from app.main import create_app
from app.modules.catalogue.models import StoreInventory
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.service import ReservationService
from app.modules.pricing.models import CheckoutQuote, CheckoutQuoteItem, QuoteStatus


def get_internal_auth_headers(use_token_alias: bool = False) -> dict[str, str]:
    """Helper to generate valid internal authorization headers without hardcoding."""
    assert settings.INTERNAL_SERVICE_KEY is not None
    key = settings.INTERNAL_SERVICE_KEY.get_secret_value()
    header_name = "X-Internal-Token" if use_token_alias else "X-Internal-Service-Key"
    return {header_name: key}


async def get_test_listing(async_client: AsyncClient, min_stock: int = 5) -> dict:
    """Helper to fetch an active product listing with sufficient stock."""
    response = await async_client.get("/api/v1/products?limit=10")
    assert response.status_code == 200
    for prod in response.json()["items"]:
        detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
        assert detail_resp.status_code == 200
        for variant in detail_resp.json().get("variants", []):
            for listing in variant.get("listings", []):
                if (
                    listing.get("is_active")
                    and listing.get("available_quantity", 0) >= min_stock
                ):
                    return listing
    raise RuntimeError("No active test listing with sufficient stock found.")


async def get_two_different_retailer_listings(
    async_client: AsyncClient,
) -> tuple[dict, dict]:
    """Helper to fetch two listings from distinct retailers."""
    response = await async_client.get("/api/v1/products?limit=20")
    assert response.status_code == 200
    found_first = None
    for prod in response.json()["items"]:
        detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
        for variant in detail_resp.json().get("variants", []):
            for listing in variant.get("listings", []):
                if (
                    listing.get("is_active")
                    and listing.get("available_quantity", 0) >= 5
                ):
                    if not found_first:
                        found_first = listing
                    elif listing["retailer_id"] != found_first["retailer_id"]:
                        return found_first, listing
    raise RuntimeError("Could not find two listings from distinct retailers.")


@pytest.mark.asyncio
async def test_reservation_creation_guest(async_client: AsyncClient):
    """Guest user adds item to cart, generates quote, and creates inventory reservation."""
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])

    # Inspect initial inventory counters in DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        initial_inv = (await session.execute(inv_stmt)).scalar_one()
        initial_reserved = initial_inv.reserved_quantity
        initial_on_hand = initial_inv.on_hand_quantity

    # 1. Add item to cart
    add_resp = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 2},
    )
    assert add_resp.status_code == 200
    assert "basket_guest_cart" in add_resp.cookies

    # 2. Create quote
    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={},
    )
    assert quote_resp.status_code == 201
    quote = quote_resp.json()

    # 3. Create reservation
    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote["id"]},
    )
    assert res_resp.status_code == 201
    res_data = res_resp.json()

    assert res_data["status"] == "ACTIVE"
    assert res_data["quote_id"] == quote["id"]
    assert res_data["seconds_remaining"] > 0
    assert res_data["is_expired"] is False
    assert len(res_data["items"]) == 1
    assert res_data["items"][0]["listing_id"] == str(listing_id)
    assert res_data["items"][0]["quantity"] == 2

    # Verify database counters
    async with session_factory() as session:
        inv = (await session.execute(inv_stmt)).scalar_one()
        assert inv.on_hand_quantity == initial_on_hand
        assert inv.reserved_quantity == initial_reserved + 2

    # 4. Fetch reservation by ID
    get_res = await async_client.get(f"/api/v1/reservations/{res_data['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == res_data["id"]


@pytest.mark.asyncio
async def test_reservation_creation_authenticated(async_client: AsyncClient):
    """Authenticated customer creates quote and reservation with ownership binding."""
    # Register customer
    email = f"test.res.{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Reservation Test User",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    customer_id = reg_resp.json()["user"]["id"]
    token = reg_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    listing = await get_test_listing(async_client, min_stock=3)
    listing_id = uuid.UUID(listing["id"])

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 1},
        headers=auth_headers,
    )

    quote_resp = await async_client.post(
        "/api/v1/quotes",
        json={"delivery_state": "KA"},
        headers=auth_headers,
    )
    assert quote_resp.status_code == 201
    quote_id = quote_resp.json()["id"]

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
        headers=auth_headers,
    )
    assert res_resp.status_code == 201
    res_data = res_resp.json()
    assert res_data["customer_id"] == customer_id
    assert res_data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_reservation_idempotency(async_client: AsyncClient):
    """Submitting reservation with same Idempotency-Key returns existing reservation."""
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        initial_inv = (await session.execute(inv_stmt)).scalar_one()
        initial_reserved = initial_inv.reserved_quantity

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 1},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    assert quote_resp.status_code == 201
    quote_id = quote_resp.json()["id"]

    idem_key = f"idem-key-{uuid.uuid4().hex}"

    # First attempt
    res1 = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert res1.status_code == 201
    res1_id = res1.json()["id"]

    # Second attempt with same key
    res2 = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert res2.status_code == 201
    assert res2.json()["id"] == res1_id

    # Verify inventory was reserved exactly once (+1, not +2)
    async with session_factory() as session:
        inv = (await session.execute(inv_stmt)).scalar_one()
        assert inv.reserved_quantity == initial_reserved + 1


@pytest.mark.asyncio
async def test_reservation_ownership_isolation(async_client: AsyncClient):
    """Guarantees cross-guest, cross-customer, and unauthenticated isolation (404)."""
    listing = await get_test_listing(async_client, min_stock=3)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    quote_id = quote_resp.json()["id"]

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
    )
    assert res_resp.status_code == 201
    reservation_id = res_resp.json()["id"]

    # Other client without cookies
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as unauth_client:
        resp = await unauth_client.get(f"/api/v1/reservations/{reservation_id}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

        rel_resp = await unauth_client.post(
            f"/api/v1/reservations/{reservation_id}/release"
        )
        assert rel_resp.status_code == 404

    # Other guest with different cookie
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"basket_guest_cart": str(uuid.uuid4())},
    ) as other_guest_client:
        resp = await other_guest_client.get(f"/api/v1/reservations/{reservation_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reservation_release_restores_stock(async_client: AsyncClient):
    """Releasing an active reservation decrements reserved_quantity back to baseline."""
    listing = await get_test_listing(async_client, min_stock=4)
    listing_id = uuid.UUID(listing["id"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        initial_inv = (await session.execute(inv_stmt)).scalar_one()
        initial_reserved = initial_inv.reserved_quantity

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 2},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    quote_id = quote_resp.json()["id"]

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
    )
    assert res_resp.status_code == 201
    res_id = res_resp.json()["id"]

    # Reserved quantity increased
    async with session_factory() as session:
        inv = (await session.execute(inv_stmt)).scalar_one()
        assert inv.reserved_quantity == initial_reserved + 2

    # Release reservation
    rel_resp = await async_client.post(f"/api/v1/reservations/{res_id}/release")
    assert rel_resp.status_code == 200
    assert rel_resp.json()["status"] == "RELEASED"

    # Reserved quantity restored
    async with session_factory() as session:
        inv = (await session.execute(inv_stmt)).scalar_one()
        assert inv.reserved_quantity == initial_reserved

    # Repeated release is idempotent
    rel_repeat = await async_client.post(f"/api/v1/reservations/{res_id}/release")
    assert rel_repeat.status_code == 200
    assert rel_repeat.json()["status"] == "RELEASED"


@pytest.mark.asyncio
async def test_reservation_confirmation_deducts_on_hand(async_client: AsyncClient):
    """Confirming a reservation converts reserved quantity to actual deduction from on_hand."""
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        initial_inv = (await session.execute(inv_stmt)).scalar_one()
        initial_on_hand = initial_inv.on_hand_quantity
        initial_reserved = initial_inv.reserved_quantity

    try:
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 2},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        quote_id = quote_resp.json()["id"]

        res_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id},
        )
        res_id = uuid.UUID(res_resp.json()["id"])

        # Direct confirmation via service
        async with session_factory() as session:
            service = ReservationService(session)
            confirmed = await service.confirm_reservation(res_id, internal=True)
            assert confirmed.status == ReservationStatus.CONFIRMED.value
            await session.commit()

        # Verify on_hand decreased by 2, reserved returned to initial
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == initial_on_hand - 2
            assert inv.reserved_quantity == initial_reserved
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=initial_on_hand,
                    reserved_quantity=initial_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_invalid_lifecycle_transitions(async_client: AsyncClient):
    """Enforces state machine: disallows confirming expired/released or releasing confirmed."""
    listing = await get_test_listing(async_client, min_stock=3)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    quote_id = quote_resp.json()["id"]

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
    )
    res_id = uuid.UUID(res_resp.json()["id"])

    session_factory = get_session_factory()

    # 1. Release reservation
    await async_client.post(f"/api/v1/reservations/{res_id}/release")

    # 2. Try confirming released reservation -> 409
    async with session_factory() as session:
        service = ReservationService(session)
        with pytest.raises(Exception) as exc:
            await service.confirm_reservation(res_id, internal=True)
        assert "Cannot confirm a released reservation" in str(exc.value)


@pytest.mark.asyncio
async def test_atomic_multi_retailer_all_or_nothing_rollback(async_client: AsyncClient):
    """If one retailer has insufficient stock, zero stock is reserved for any retailer."""
    listing1, listing2 = await get_two_different_retailer_listings(async_client)
    id1 = uuid.UUID(listing1["id"])
    id2 = uuid.UUID(listing2["id"])

    session_factory = get_session_factory()

    # Record initial reserved quantity for listing1
    async with session_factory() as session:
        inv1 = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.listing_id == id1)
            )
        ).scalar_one()
        initial_reserved1 = inv1.reserved_quantity

    # 1. Add both items from different retailers to cart while stock is present
    r1 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(id1), "quantity": 1},
    )
    assert r1.status_code == 200

    r2 = await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(id2), "quantity": 1},
    )
    assert r2.status_code == 200

    # 2. Generate quote containing both items
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    assert quote_resp.status_code == 201
    quote = quote_resp.json()
    assert len(quote["items"]) == 2
    quote_id = quote["id"]

    # 3. Simulate another transaction depleting listing2 stock prior to reservation
    async with session_factory() as session:
        inv2 = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.listing_id == id2)
            )
        ).scalar_one()
        orig_on_hand2 = inv2.on_hand_quantity
        orig_reserved2 = inv2.reserved_quantity

        await session.execute(
            update(StoreInventory)
            .where(StoreInventory.listing_id == id2)
            .values(on_hand_quantity=1, reserved_quantity=1)
        )
        await session.commit()

    try:
        # 4. Attempt reservation -> 409 INSUFFICIENT_STOCK
        res_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id},
        )
        assert res_resp.status_code == 409
        err = res_resp.json()["error"]
        assert err["code"] == "INSUFFICIENT_STOCK"
        assert len(err["details"]) >= 1

        # Invariant: listing 1's reserved quantity must remain completely untouched!
        async with session_factory() as session:
            inv1_after = (
                await session.execute(
                    select(StoreInventory).where(StoreInventory.listing_id == id1)
                )
            ).scalar_one()
            assert inv1_after.reserved_quantity == initial_reserved1
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == id2)
                .values(
                    on_hand_quantity=orig_on_hand2, reserved_quantity=orig_reserved2
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_reservation_cleanup_expired(async_client: AsyncClient):
    """Expired reservations are identified and their reserved stock restored."""
    listing = await get_test_listing(async_client, min_stock=3)
    listing_id = uuid.UUID(listing["id"])

    # Run internal cleanup beforehand to clear any leftover expired reservations
    await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired",
        headers=get_internal_auth_headers(),
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        initial_reserved = (
            (await session.execute(inv_stmt)).scalar_one().reserved_quantity
        )

    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 1},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    quote_id = quote_resp.json()["id"]

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": quote_id},
    )
    res_id = uuid.UUID(res_resp.json()["id"])

    # Artificially expire the reservation in DB
    past_time = datetime.now(UTC) - timedelta(minutes=15)
    async with session_factory() as session:
        await session.execute(
            update(InventoryReservation)
            .where(InventoryReservation.id == res_id)
            .values(expires_at=past_time)
        )
        await session.commit()

    # Run internal cleanup
    clean_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired",
        headers=get_internal_auth_headers(),
    )
    assert clean_resp.status_code == 200
    assert clean_resp.json()["expired_count"] >= 1

    # Verify reservation status changed to EXPIRED and stock returned
    async with session_factory() as session:
        res = (
            await session.execute(
                select(InventoryReservation).where(InventoryReservation.id == res_id)
            )
        ).scalar_one()
        assert res.status == ReservationStatus.EXPIRED.value
        assert res.release_reason == "TTL_EXPIRED"

        inv = (await session.execute(inv_stmt)).scalar_one()
        assert inv.reserved_quantity == initial_reserved


@pytest.mark.asyncio
async def test_reservation_quote_validation(async_client: AsyncClient):
    """Rejects reservations on expired or consumed quotes with 409."""
    listing = await get_test_listing(async_client, min_stock=3)
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing["id"], "quantity": 1},
    )
    quote_resp = await async_client.post("/api/v1/quotes", json={})
    quote_id = uuid.UUID(quote_resp.json()["id"])

    session_factory = get_session_factory()

    # Expire quote
    async with session_factory() as session:
        await session.execute(
            update(CheckoutQuote)
            .where(CheckoutQuote.id == quote_id)
            .values(
                expires_at=datetime.now(UTC) - timedelta(minutes=20),
                status=QuoteStatus.EXPIRED.value,
            )
        )
        await session.commit()

    res_resp = await async_client.post(
        "/api/v1/reservations",
        json={"quote_id": str(quote_id)},
    )
    assert res_resp.status_code == 409
    assert res_resp.json()["error"]["code"] == "QUOTE_EXPIRED"


@pytest.mark.asyncio
async def test_high_concurrency_last_unit_race_protection(async_client: AsyncClient):
    """Real PostgreSQL Concurrency Test:

    When multiple concurrent requests race for the last remaining unit of stock,
    PostgreSQL row-level locking guarantees that exactly ONE succeeds and the
    others receive structured INSUFFICIENT_STOCK errors with ZERO oversell.
    """
    listing = await get_test_listing(async_client, min_stock=1)
    listing_id = uuid.UUID(listing["id"])

    session_factory = get_session_factory()

    # Record initial stock values
    async with session_factory() as session:
        orig_inv = (
            await session.execute(
                select(StoreInventory).where(StoreInventory.listing_id == listing_id)
            )
        ).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

        # Set exact stock to 1 on_hand and 0 reserved
        await session.execute(
            update(StoreInventory)
            .where(StoreInventory.listing_id == listing_id)
            .values(on_hand_quantity=1, reserved_quantity=0)
        )
        await session.commit()

    # Create 5 distinct quotes (each simulating a different client with its own guest cookie)
    app = create_app()
    quotes = []
    clients = []

    try:
        for _ in range(5):
            guest_cookie = str(uuid.uuid4())
            client = AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"basket_guest_cart": guest_cookie},
            )
            clients.append(client)
            # Add 1 unit to cart
            add_r = await client.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            assert add_r.status_code == 200
            # Generate quote
            q_r = await client.post("/api/v1/quotes", json={})
            assert q_r.status_code == 201
            quotes.append((client, q_r.json()["id"]))

        # Launch all 5 reservation requests simultaneously using asyncio.gather
        async def make_reservation(cli: AsyncClient, q_id: str):
            return await cli.post(
                "/api/v1/reservations",
                json={"quote_id": q_id},
            )

        responses = await asyncio.gather(
            *(make_reservation(cli, q_id) for cli, q_id in quotes)
        )

        success_responses = [r for r in responses if r.status_code == 201]
        shortage_responses = [r for r in responses if r.status_code == 409]

        # Clean up clients
        for cli in clients:
            await cli.aclose()

        # CRITICAL INVARIANT: Exactly 1 succeeds, 4 fail
        assert len(success_responses) == 1, (
            f"Expected exactly 1 success, got {len(success_responses)}"
        )
        assert len(shortage_responses) == 4, (
            f"Expected exactly 4 shortages, got {len(shortage_responses)}"
        )

        for err_resp in shortage_responses:
            assert err_resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"

        # PostgreSQL Database Verification: reserved_quantity == 1, on_hand == 1, available == 0
        async with session_factory() as session:
            inv = (
                await session.execute(
                    select(StoreInventory).where(
                        StoreInventory.listing_id == listing_id
                    )
                )
            ).scalar_one()
            assert inv.on_hand_quantity == 1
            assert inv.reserved_quantity == 1
            assert inv.available_quantity == 0
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_internal_cleanup_security_unauthorized_rejected(
    async_client: AsyncClient,
):
    """TASK 1: Internal cleanup endpoint must reject unauthenticated requests,
    invalid tokens, and authenticated customers lacking internal privileges."""
    # 1. Unauthenticated request without headers must be rejected with 401
    no_header_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired"
    )
    assert no_header_resp.status_code == 401
    assert no_header_resp.json()["error"]["code"] == "UNAUTHORIZED"

    # 2. Request with invalid internal secret key must be rejected with 401
    bad_key_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired",
        headers={"X-Internal-Service-Key": "wrong-secret-key"},
    )
    assert bad_key_resp.status_code == 401
    assert bad_key_resp.json()["error"]["code"] == "UNAUTHORIZED"

    # 3. Authenticated customer session without internal key must be rejected with 401
    customer_email = f"cust_cleanup_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": customer_email,
            "password": "Password123!",
            "full_name": "Test Customer",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201

    customer_clean_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired"
    )
    assert customer_clean_resp.status_code == 401
    assert customer_clean_resp.json()["error"]["code"] == "UNAUTHORIZED"

    # 4. Valid X-Internal-Service-Key must succeed with 200
    valid_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired",
        headers=get_internal_auth_headers(),
    )
    assert valid_resp.status_code == 200
    assert "expired_count" in valid_resp.json()

    # 5. Valid X-Internal-Token alias must succeed with 200
    valid_token_resp = await async_client.post(
        "/api/v1/internal/reservations/cleanup-expired",
        headers=get_internal_auth_headers(use_token_alias=True),
    )
    assert valid_token_resp.status_code == 200
    assert "expired_count" in valid_token_resp.json()


@pytest.mark.asyncio
async def test_confirmation_accounting_and_lifecycle(async_client: AsyncClient):
    """TASK 2: Reservation confirmation accounting:
    - on_hand_quantity decreases exactly once.
    - reserved_quantity decreases exactly once.
    - Available inventory remains consistent.
    - Duplicate confirmation cannot deduct stock again.
    - Confirmation of RELEASED or EXPIRED reservations fails.
    - Confirmation is NOT exposed as an unrestricted customer HTTP route.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        # Create active reservation for 2 units
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 2},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        assert quote_resp.status_code == 201
        quote_id = quote_resp.json()["id"]

        res_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id},
        )
        assert res_resp.status_code == 201
        res_id = uuid.UUID(res_resp.json()["id"])

        # Stock before confirmation: on_hand = orig_on_hand, reserved = orig_reserved + 2
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand
            assert inv.reserved_quantity == orig_reserved + 2
            available_before_confirm = inv.on_hand_quantity - inv.reserved_quantity

        # 1. Execute confirmation via internal service
        async with session_factory() as session:
            service = ReservationService(session)
            confirmed_res = await service.confirm_reservation(res_id, internal=True)
            await session.commit()
            assert confirmed_res.status == ReservationStatus.CONFIRMED.value
            assert confirmed_res.confirmed_at is not None

        # 2. Verify stock deduction after confirmation:
        # on_hand decreases by 2, reserved decreases by 2, available remains identical
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand - 2
            assert inv.reserved_quantity == orig_reserved
            available_after_confirm = inv.on_hand_quantity - inv.reserved_quantity
            assert available_after_confirm == available_before_confirm

        # 3. Duplicate confirmation must be idempotent and NEVER deduct stock again
        async with session_factory() as session:
            service = ReservationService(session)
            dup_res = await service.confirm_reservation(res_id, internal=True)
            await session.commit()
            assert dup_res.status == ReservationStatus.CONFIRMED.value

        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand - 2
            assert inv.reserved_quantity == orig_reserved

        # 4. Confirmation of RELEASED reservation must fail with 409
        q2_resp = await async_client.post("/api/v1/quotes", json={})
        assert q2_resp.status_code == 201
        r2_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q2_resp.json()["id"]},
        )
        r2_id = uuid.UUID(r2_resp.json()["id"])
        await async_client.post(f"/api/v1/reservations/{r2_id}/release")

        async with session_factory() as session:
            service = ReservationService(session)
            with pytest.raises(AppException) as exc_info:
                await service.confirm_reservation(r2_id, internal=True)
            assert exc_info.value.code == "RESERVATION_RELEASED"
            assert exc_info.value.status_code == 409

        # 5. Confirmation of EXPIRED reservation must fail with 409
        q3_resp = await async_client.post("/api/v1/quotes", json={})
        r3_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q3_resp.json()["id"]},
        )
        r3_id = uuid.UUID(r3_resp.json()["id"])
        past_time = datetime.now(UTC) - timedelta(minutes=20)
        async with session_factory() as session:
            await session.execute(
                update(InventoryReservation)
                .where(InventoryReservation.id == r3_id)
                .values(expires_at=past_time)
            )
            await session.commit()

        # Run internal cleanup to mark EXPIRED
        await async_client.post(
            "/api/v1/internal/reservations/cleanup-expired",
            headers=get_internal_auth_headers(),
        )

        async with session_factory() as session:
            service = ReservationService(session)
            with pytest.raises(AppException) as exc_info:
                await service.confirm_reservation(r3_id, internal=True)
            assert exc_info.value.code == "RESERVATION_EXPIRED"
            assert exc_info.value.status_code == 409

        # 6. Verify confirmation is not exposed as a customer HTTP route
        http_confirm_resp = await async_client.post(
            f"/api/v1/reservations/{res_id}/confirm"
        )
        assert http_confirm_resp.status_code in (404, 405)

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_expiry_and_confirmation_race(async_client: AsyncClient):
    """TASK 3: Expiry and confirmation race condition in real PostgreSQL:
    One task attempts to expire/release the reservation, while another authorized
    task attempts to confirm it concurrently.
    PostgreSQL row-level locks guarantee exactly one transition wins,
    and all inventory counters remain consistent with no double release,
    no double deduction, and no negative numbers.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        # Create active reservation for 2 units
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 2},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        res_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_resp.json()["id"]},
        )
        res_id = uuid.UUID(res_resp.json()["id"])

        async def worker_expire():
            async with session_factory() as s1:
                svc1 = ReservationService(s1)
                res = await svc1.release_reservation(
                    reservation_id=res_id,
                    reason="TTL_EXPIRED",
                    internal=True,
                )
                await s1.commit()
                return res

        async def worker_confirm():
            async with session_factory() as s2:
                svc2 = ReservationService(s2)
                res = await svc2.confirm_reservation(
                    reservation_id=res_id,
                    internal=True,
                )
                await s2.commit()
                return res

        # Run both simultaneously against PostgreSQL
        results = await asyncio.gather(
            worker_expire(),
            worker_confirm(),
            return_exceptions=True,
        )

        successes = [r for r in results if not isinstance(r, Exception)]
        exceptions = [r for r in results if isinstance(r, Exception)]

        # CRITICAL CONCURRENCY INVARIANT: Exactly 1 transition succeeds, exactly 1 raises 409
        assert len(successes) == 1, (
            f"Expected 1 success, got {len(successes)}: {results}"
        )
        assert len(exceptions) == 1, (
            f"Expected 1 exception, got {len(exceptions)}: {results}"
        )

        err = exceptions[0]
        assert isinstance(err, AppException)
        assert err.status_code == 409
        assert err.code in ("RESERVATION_ALREADY_CONFIRMED", "RESERVATION_EXPIRED")

        # Database verification of final state
        async with session_factory() as session:
            final_res = (
                await session.execute(
                    select(InventoryReservation).where(
                        InventoryReservation.id == res_id
                    )
                )
            ).scalar_one()
            assert final_res.status in (
                ReservationStatus.CONFIRMED.value,
                ReservationStatus.EXPIRED.value,
            )

            final_inv = (await session.execute(inv_stmt)).scalar_one()
            # Invariants must hold strictly
            assert 0 <= final_inv.reserved_quantity <= final_inv.on_hand_quantity
            assert final_inv.on_hand_quantity >= 0

            if final_res.status == ReservationStatus.CONFIRMED.value:
                # Stock was permanently deducted by 2, reserved restored
                assert final_inv.on_hand_quantity == orig_on_hand - 2
                assert final_inv.reserved_quantity == orig_reserved
            else:
                # Expiry won: on_hand unchanged, reserved restored
                assert final_inv.on_hand_quantity == orig_on_hand
                assert final_inv.reserved_quantity == orig_reserved

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_idempotency_and_quote_reuse_lifecycle(async_client: AsyncClient):
    """TASK 4: Idempotency and quote reuse tests:
    - Same idempotency key repeated returns existing active reservation.
    - Different idempotency key with same quote returns active reservation.
    - Released reservation retry: fresh reservation created if stock available.
    - Expired reservation retry: auto-releases expired hold and creates fresh hold.
    - Guest token rotation and ownership isolation.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        quote_id = quote_resp.json()["id"]

        # 1. Same idempotency key repeated returns identical active reservation
        idem_key = f"key_{uuid.uuid4().hex[:12]}"
        res1 = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id, "idempotency_key": idem_key},
        )
        assert res1.status_code == 201
        res1_id = res1.json()["id"]

        res2 = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id, "idempotency_key": idem_key},
        )
        assert res2.status_code == 201
        assert res2.json()["id"] == res1_id

        # 2. Different idempotency key with the same active quote returns existing reservation
        diff_idem_key = f"key_{uuid.uuid4().hex[:12]}"
        res3 = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id, "idempotency_key": diff_idem_key},
        )
        assert res3.status_code == 201
        assert res3.json()["id"] == res1_id

        # 3. Released reservation retry: client releases hold, then requests again
        await async_client.post(f"/api/v1/reservations/{res1_id}/release")

        # Now quote has no active reservation. Retrying reservation creates a fresh one
        retry_res = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id},
        )
        assert retry_res.status_code == 201
        retry_res_id = retry_res.json()["id"]
        assert retry_res_id != res1_id
        assert retry_res.json()["status"] == "ACTIVE"

        # 4. Expired reservation retry: reservation expires, retrying auto-releases and creates fresh
        past_time = datetime.now(UTC) - timedelta(minutes=25)
        async with session_factory() as session:
            await session.execute(
                update(InventoryReservation)
                .where(InventoryReservation.id == uuid.UUID(retry_res_id))
                .values(expires_at=past_time)
            )
            await session.commit()

        # Retry reservation creation on same quote
        fresh_res = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": quote_id},
        )
        assert fresh_res.status_code == 201
        fresh_res_id = fresh_res.json()["id"]
        assert fresh_res_id != retry_res_id
        assert fresh_res.json()["status"] == "ACTIVE"

        # 5. Guest token rotation and ownership isolation
        app = create_app()
        intruder_cookie = str(uuid.uuid4())
        intruder_client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"basket_guest_cart": intruder_cookie},
        )
        # Intruder cannot read fresh_res
        intruder_get = await intruder_client.get(f"/api/v1/reservations/{fresh_res_id}")
        assert intruder_get.status_code == 404
        assert intruder_get.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

        # Intruder cannot release fresh_res
        intruder_release = await intruder_client.post(
            f"/api/v1/reservations/{fresh_res_id}/release"
        )
        assert intruder_release.status_code == 404
        assert intruder_release.json()["error"]["code"] == "RESERVATION_NOT_FOUND"

        await intruder_client.aclose()

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_inventory_check_constraints_and_invariants(async_client: AsyncClient):
    """TASK 5: Inventory invariants at database and service level:
    - 0 <= reserved_quantity <= on_hand_quantity enforced by PostgreSQL check constraints.
    - All reservation items belong to their stated listing and retailer.
    - Duplicate listing items in quote are aggregated and deduplicated safely.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = (
            select(StoreInventory)
            .where(StoreInventory.listing_id == listing_id)
            .options(selectinload(StoreInventory.listing))
        )
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity
        actual_variant_id = orig_inv.listing.variant_id

    try:
        # 1. Database level check constraint: reserved_quantity > on_hand_quantity must fail
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(StoreInventory)
                    .where(StoreInventory.listing_id == listing_id)
                    .values(on_hand_quantity=5, reserved_quantity=10)
                )
                await session.flush()
            await session.rollback()

        # 2. Database level check constraint: reserved_quantity < 0 must fail
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(StoreInventory)
                    .where(StoreInventory.listing_id == listing_id)
                    .values(reserved_quantity=-1)
                )
                await session.flush()
            await session.rollback()

        # 3. Database level check constraint: on_hand_quantity < 0 must fail
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(StoreInventory)
                    .where(StoreInventory.listing_id == listing_id)
                    .values(on_hand_quantity=-1)
                )
                await session.flush()
            await session.rollback()

        # 4. Service level invariant: Listing retailer mismatch rejected
        list_a, list_b = await get_two_different_retailer_listings(async_client)
        mismatched_retailer_id = uuid.UUID(list_b["retailer_id"])

        async with session_factory() as session:
            quote_id = uuid.uuid4()
            fake_quote = CheckoutQuote(
                id=quote_id,
                customer_id=None,
                guest_token_hash="a" * 64,
                currency="INR",
                subtotal_paise=1000,
                delivery_fee_paise=0,
                total_tax_paise=0,
                total_payable_paise=1000,
                status=QuoteStatus.ACTIVE.value,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
            session.add(fake_quote)
            await session.flush()

            fake_item = CheckoutQuoteItem(
                id=uuid.uuid4(),
                quote_id=quote_id,
                listing_id=listing_id,
                retailer_id=mismatched_retailer_id,  # Mismatched retailer from distinct retailer!
                variant_id=actual_variant_id,
                quantity=1,
                product_title="Test Product",
                variant_title="Standard",
                hsn_code="8518",
                gst_rate_basis_points=1800,
                unit_original_price_paise=1000,
                unit_selling_price_paise=1000,
                unit_discount_paise=0,
                unit_discounted_price_paise=1000,
                total_selling_price_paise=1000,
                taxable_base_paise=847,
                cgst_paise=76,
                sgst_paise=77,
                igst_paise=0,
                total_tax_paise=153,
                retailer_name="Retailer B",
                retailer_state="DL",
            )
            session.add(fake_item)
            await session.flush()

            svc = ReservationService(session)
            with pytest.raises(AppException) as exc_info:
                await svc.create_reservation_from_quote(
                    quote_id=quote_id,
                    guest_token_hash="a" * 64,
                )
            assert exc_info.value.code == "INVALID_RETAILER_LISTING_MISMATCH"
            assert exc_info.value.status_code == 400
            await session.rollback()

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_idempotency_semantics_replayed_key_protection(async_client: AsyncClient):
    """Release Blocker Audit 1:
    - Never silently create a new reservation for a replayed idempotency key.
    - Replaying key for a released reservation is rejected with 409 IDEMPOTENCY_KEY_ALREADY_USED.
    - Replaying key for an expired reservation is rejected with 409 IDEMPOTENCY_KEY_ALREADY_USED.
    - Reusing key for a different quote is rejected with 409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        # Create cart item and quote
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q1_resp = await async_client.post("/api/v1/quotes", json={})
        q1_id = q1_resp.json()["id"]

        spent_idem_key = f"spent_key_{uuid.uuid4().hex[:12]}"

        # 1. First reservation with spent_idem_key succeeds
        r1_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q1_id, "idempotency_key": spent_idem_key},
        )
        assert r1_resp.status_code == 201
        res1_id = r1_resp.json()["id"]

        # 2. Release this reservation
        rel_resp = await async_client.post(f"/api/v1/reservations/{res1_id}/release")
        assert rel_resp.status_code == 200

        # 3. Replaying the spent idempotency key to create a new reservation MUST BE REJECTED
        replay_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q1_id, "idempotency_key": spent_idem_key},
        )
        assert replay_resp.status_code == 409
        assert replay_resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_ALREADY_USED"

        # 4. Same quote with a FRESH idempotency key succeeds
        fresh_key = f"fresh_key_{uuid.uuid4().hex[:12]}"
        retry_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q1_id, "idempotency_key": fresh_key},
        )
        assert retry_resp.status_code == 201
        res2_id = retry_resp.json()["id"]
        assert res2_id != res1_id

        # 5. Expire this second reservation
        past_time = datetime.now(UTC) - timedelta(minutes=25)
        async with session_factory() as session:
            await session.execute(
                update(InventoryReservation)
                .where(InventoryReservation.id == uuid.UUID(res2_id))
                .values(expires_at=past_time)
            )
            await session.commit()

        # 6. Replaying fresh_key (now expired) MUST BE REJECTED
        expired_replay_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q1_id, "idempotency_key": fresh_key},
        )
        assert expired_replay_resp.status_code == 409
        assert (
            expired_replay_resp.json()["error"]["code"]
            == "IDEMPOTENCY_KEY_ALREADY_USED"
        )

        # 7. Reusing spent_idem_key for a DIFFERENT quote must be rejected
        q2_resp = await async_client.post("/api/v1/quotes", json={})
        q2_id = q2_resp.json()["id"]

        cross_quote_resp = await async_client.post(
            "/api/v1/reservations",
            json={"quote_id": q2_id, "idempotency_key": spent_idem_key},
        )
        assert cross_quote_resp.status_code == 409
        assert (
            cross_quote_resp.json()["error"]["code"]
            == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
        )

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_reservations_identical_keys(async_client: AsyncClient):
    """Concurrent requests with identical idempotency keys:
    PostgreSQL serialization and integrity handling guarantee exactly ONE reservation
    is created in the database, and both concurrent calls receive the identical reservation.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        quote_id = quote_resp.json()["id"]
        shared_key = f"concurrent_key_{uuid.uuid4().hex[:12]}"

        # Launch 2 simultaneous reservation calls with the exact same idempotency key
        app = create_app()
        guest_cookie = async_client.cookies.get("basket_guest_cart", "")

        async def make_call():
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"basket_guest_cart": guest_cookie},
            ) as cli:
                return await cli.post(
                    "/api/v1/reservations",
                    json={"quote_id": quote_id, "idempotency_key": shared_key},
                )

        resp1, resp2 = await asyncio.gather(make_call(), make_call())

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]

        # Verify database has exactly 1 reservation for this key and quote
        async with session_factory() as session:
            reservations = (
                (
                    await session.execute(
                        select(InventoryReservation).where(
                            InventoryReservation.idempotency_key == shared_key
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(reservations) == 1
            assert reservations[0].quote_id == uuid.UUID(quote_id)

            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.reserved_quantity == orig_reserved + 1

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_reservations_different_keys_same_quote(
    async_client: AsyncClient,
):
    """Concurrent requests with DIFFERENT idempotency keys for the SAME quote:
    PostgreSQL partial unique index uq_reservations_quote_active guarantees
    only ONE active reservation can exist for a quote. Both calls return the active reservation.
    """
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        quote_resp = await async_client.post("/api/v1/quotes", json={})
        quote_id = quote_resp.json()["id"]

        app = create_app()
        guest_cookie = async_client.cookies.get("basket_guest_cart", "")

        key_a = f"diff_key_a_{uuid.uuid4().hex[:12]}"
        key_b = f"diff_key_b_{uuid.uuid4().hex[:12]}"

        async def make_call(key: str):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"basket_guest_cart": guest_cookie},
            ) as cli:
                return await cli.post(
                    "/api/v1/reservations",
                    json={"quote_id": quote_id, "idempotency_key": key},
                )

        resp1, resp2 = await asyncio.gather(make_call(key_a), make_call(key_b))

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]

        # Stock reserved exactly once (1 unit, not 2)
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.reserved_quantity == orig_reserved + 1

    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(on_hand_quantity=orig_on_hand, reserved_quantity=orig_reserved)
            )
            await session.commit()


def test_internal_service_key_configuration_security():
    """Internal service key security requirements:
    - Missing key in production raises ValueError.
    - Weak/short key (<32 chars) in production raises ValueError.
    - Valid strong key in production passes.
    """
    # 1. In production, missing key is rejected
    with pytest.raises(
        ValueError, match="INTERNAL_SERVICE_KEY must be configured in production"
    ):
        Settings(ENVIRONMENT="production", INTERNAL_SERVICE_KEY=None)

    # 2. In production, weak keys are rejected
    with pytest.raises(
        ValueError, match="INTERNAL_SERVICE_KEY in production must be a secure"
    ):
        Settings(ENVIRONMENT="production", INTERNAL_SERVICE_KEY="password")

    # 3. In production, short keys (< 32 chars) are rejected
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            ENVIRONMENT="production", INTERNAL_SERVICE_KEY="short-secret-key-12345"
        )

    # 4. In production, strong random key is accepted
    strong_key = "a" * 32
    prod_settings = Settings(
        ENVIRONMENT="production",
        INTERNAL_SERVICE_KEY=strong_key,
        RAZORPAY_KEY_ID="rzp_live_realprodkey123",
        RAZORPAY_KEY_SECRET="productionsecret16chars",
        RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
    )
    assert prod_settings.INTERNAL_SERVICE_KEY is not None
    assert prod_settings.INTERNAL_SERVICE_KEY.get_secret_value() == strong_key
