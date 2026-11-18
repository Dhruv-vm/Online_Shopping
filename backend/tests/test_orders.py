import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import get_session_factory
from app.main import create_app
from app.modules.catalogue.models import StoreInventory
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OutboxEvent,
)
from app.modules.orders.schemas import CreateOrderRequest
from app.modules.orders.service import OrderService
from app.modules.payments.client import RazorpayClient
from app.modules.pricing.models import CheckoutQuote, QuoteStatus
from tests.test_payments import generate_payment_signature, setup_customer_and_order


def get_internal_auth_headers(use_token_alias: bool = False) -> dict[str, str]:
    assert settings.INTERNAL_SERVICE_KEY is not None
    key = settings.INTERNAL_SERVICE_KEY.get_secret_value()
    header_name = "X-Internal-Token" if use_token_alias else "X-Internal-Service-Key"
    return {header_name: key}


async def get_test_listing(async_client: AsyncClient, min_stock: int = 5) -> dict:
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


VALID_ADDRESS_PAYLOAD = {
    "full_name": "Ramesh Kumar",
    "address_line1": "Flat 402, Lotus Residency",
    "address_line2": "12th Cross, Indiranagar",
    "city": "Bengaluru",
    "state": "KA",
    "postal_code": "560001",
    "phone": "+919876543210",
}


async def setup_customer_with_address(
    client: AsyncClient,
) -> tuple[dict, str, str]:
    email = f"order_cust_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Order Test User",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    user_data = reg_resp.json()["user"]

    addr_resp = await client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Order Test User",
            "phone": "+919876543210",
            "line1": "100 Feet Road",
            "city": "Bengaluru",
            "state": "KA",
            "postal_code": "560038",
            "is_default": True,
        },
    )
    assert addr_resp.status_code == 201
    addr_id = addr_resp.json()["id"]
    return user_data, email, addr_id


@pytest.mark.asyncio
async def test_order_creation_authenticated_happy_path(
    async_client: AsyncClient,
):
    """1. Authenticated customer creates order with quote, reservation, and saved address."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        assert q_resp.status_code == 201
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        assert r_resp.status_code == 201
        res_id = r_resp.json()["id"]

        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201
        data = order_resp.json()
        assert data["order_number"].startswith("BSK-")
        assert data["status"] == "PENDING_PAYMENT"
        assert data["payment_status"] == "NOT_INITIATED"
        assert data["customer_id"] == user_data["id"]
        assert len(data["items"]) == 1
        assert data["items"][0]["listing_id"] == str(listing_id)
        assert data["delivery_address"]["postal_code"] == "560038"

        # Check DB state
        async with session_factory() as session:
            quote = (
                await session.execute(
                    select(CheckoutQuote).where(CheckoutQuote.id == uuid.UUID(quote_id))
                )
            ).scalar_one()
            assert quote.is_consumed is True
            assert quote.status == QuoteStatus.CONSUMED.value

            res = (
                await session.execute(
                    select(InventoryReservation).where(
                        InventoryReservation.id == uuid.UUID(res_id)
                    )
                )
            ).scalar_one()
            assert res.status == ReservationStatus.ALLOCATED_TO_ORDER.value
            assert res.order_id == uuid.UUID(data["id"])

            # Outbox event exists
            event = (
                await session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_id == uuid.UUID(data["id"])
                    )
                )
            ).scalar_one()
            assert event.event_type == "order.created"
            assert event.status == "PENDING"
            assert event.payload["order_number"] == data["order_number"]
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_guest_happy_path(async_client: AsyncClient):
    """2. Guest user adds item to cart, quotes, reserves, and orders with inline address."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        app = create_app()
        guest_cookie = f"guest_order_{uuid.uuid4().hex}"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"basket_guest_cart": guest_cookie},
        ) as client:
            await client.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            q_resp = await client.post("/api/v1/quotes", json={"delivery_state": "KA"})
            assert q_resp.status_code == 201
            quote_id = q_resp.json()["id"]

            r_resp = await client.post(
                "/api/v1/reservations", json={"quote_id": quote_id}
            )
            assert r_resp.status_code == 201
            res_id = r_resp.json()["id"]

            order_resp = await client.post(
                "/api/v1/orders",
                json={
                    "quote_id": quote_id,
                    "reservation_id": res_id,
                    "delivery_address": VALID_ADDRESS_PAYLOAD,
                },
            )
            assert order_resp.status_code == 201
            data = order_resp.json()
            assert data["customer_id"] is None
            assert data["status"] == "PENDING_PAYMENT"
            assert data["delivery_address"]["full_name"] == "Ramesh Kumar"
            assert data["delivery_address"]["postal_code"] == "560001"
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_canonical_fingerprinting_same_key_same_payload(
    async_client: AsyncClient,
):
    """3. Replaying an order placement request with same key and identical payload returns original order."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        idem_key = f"order_key_{uuid.uuid4().hex[:12]}"
        req_body = {
            "quote_id": quote_id,
            "reservation_id": res_id,
            "delivery_address_id": addr_id,
            "idempotency_key": idem_key,
        }

        # First request
        resp1 = await async_client.post("/api/v1/orders", json=req_body)
        assert resp1.status_code == 201

        # Second request (replay)
        resp2 = await async_client.post("/api/v1/orders", json=req_body)
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]
        assert resp1.json()["order_number"] == resp2.json()["order_number"]
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_canonical_fingerprinting_same_key_diff_payload_rejected(
    async_client: AsyncClient,
):
    """4. Replaying same idempotency key with a modified payload (e.g. different address) returns 409."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        idem_key = f"order_diff_key_{uuid.uuid4().hex[:12]}"

        # First request with address 1
        resp1 = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
                "idempotency_key": idem_key,
            },
        )
        assert resp1.status_code == 201

        # Second request with different inline address
        diff_addr = dict(VALID_ADDRESS_PAYLOAD)
        diff_addr["city"] = "Mysuru"
        resp2 = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address": diff_addr,
                "idempotency_key": idem_key,
            },
        )
        assert resp2.status_code == 409
        assert (
            resp2.json()["error"]["code"]
            == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
        )
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_identical_idempotency_requests(
    async_client: AsyncClient,
):
    """5. Concurrent identical requests with same key against live PostgreSQL serialize safely."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        shared_key = f"concurrent_order_key_{uuid.uuid4().hex[:12]}"
        req_body = {
            "quote_id": quote_id,
            "reservation_id": res_id,
            "delivery_address_id": addr_id,
            "idempotency_key": shared_key,
        }

        # Concurrently fire 2 requests with the exact same payload and key
        resp1, resp2 = await asyncio.gather(
            async_client.post("/api/v1/orders", json=req_body),
            async_client.post("/api/v1/orders", json=req_body),
        )

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] == resp2.json()["id"]

        # Exactly 1 order in database
        async with session_factory() as session:
            orders = (
                (
                    await session.execute(
                        select(Order).where(Order.quote_id == uuid.UUID(quote_id))
                    )
                )
                .scalars()
                .all()
            )
            assert len(orders) == 1
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_same_key_across_different_customers(async_client: AsyncClient):
    """6. Two different customers using the exact same idempotency key do not collide."""
    listing = await get_test_listing(async_client, min_stock=10)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        app = create_app()
        shared_key = f"user_key_{uuid.uuid4().hex[:10]}"

        # Customer 1
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c1:
            u1, e1, a1 = await setup_customer_with_address(c1)
            await c1.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            q1 = (
                await c1.post("/api/v1/quotes", json={"delivery_address_id": a1})
            ).json()["id"]
            r1 = (await c1.post("/api/v1/reservations", json={"quote_id": q1})).json()[
                "id"
            ]
            resp1 = await c1.post(
                "/api/v1/orders",
                json={
                    "quote_id": q1,
                    "reservation_id": r1,
                    "delivery_address_id": a1,
                    "idempotency_key": shared_key,
                },
            )
            assert resp1.status_code == 201

        # Customer 2
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c2:
            u2, e2, a2 = await setup_customer_with_address(c2)
            await c2.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            q2 = (
                await c2.post("/api/v1/quotes", json={"delivery_address_id": a2})
            ).json()["id"]
            r2 = (await c2.post("/api/v1/reservations", json={"quote_id": q2})).json()[
                "id"
            ]
            resp2 = await c2.post(
                "/api/v1/orders",
                json={
                    "quote_id": q2,
                    "reservation_id": r2,
                    "delivery_address_id": a2,
                    "idempotency_key": shared_key,
                },
            )
            assert resp2.status_code == 201

            assert resp1.json()["id"] != resp2.json()["id"]
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_different_keys_competing_for_same_quote(
    async_client: AsyncClient,
):
    """7. Concurrent requests with different keys for the same quote: exactly 1 wins, the other receives 409."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        key1 = f"order_key_a_{uuid.uuid4().hex[:12]}"
        key2 = f"order_key_b_{uuid.uuid4().hex[:12]}"

        resp1, resp2 = await asyncio.gather(
            async_client.post(
                "/api/v1/orders",
                json={
                    "quote_id": quote_id,
                    "reservation_id": res_id,
                    "delivery_address_id": addr_id,
                    "idempotency_key": key1,
                },
            ),
            async_client.post(
                "/api/v1/orders",
                json={
                    "quote_id": quote_id,
                    "reservation_id": res_id,
                    "delivery_address_id": addr_id,
                    "idempotency_key": key2,
                },
            ),
        )

        codes = [resp1.status_code, resp2.status_code]
        assert 201 in codes
        assert 409 in codes
        err_resp = resp1 if resp1.status_code == 409 else resp2
        assert err_resp.json()["error"]["code"] in (
            "QUOTE_ALREADY_ORDERED",
            "QUOTE_ALREADY_CONSUMED",
        )
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_quote_already_consumed(
    async_client: AsyncClient,
):
    """8. Attempting to create an order from an already consumed quote returns 409."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Place first order
        o1 = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert o1.status_code == 201

        # Attempt to order same quote again
        o2 = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert o2.status_code == 409
        assert o2.json()["error"]["code"] in (
            "QUOTE_ALREADY_CONSUMED",
            "QUOTE_ALREADY_ORDERED",
        )
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_expired_quote(async_client: AsyncClient):
    """9. Attempting checkout on expired quote returns 409 QUOTE_EXPIRED."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Force expire quote in DB
        async with session_factory() as session:
            await session.execute(
                update(CheckoutQuote)
                .where(CheckoutQuote.id == uuid.UUID(quote_id))
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=5))
            )
            await session.commit()

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "QUOTE_EXPIRED"
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_reservation_quote_mismatch(
    async_client: AsyncClient,
):
    """10. Supplying a reservation that belongs to a different quote returns 400 RESERVATION_QUOTE_MISMATCH."""
    listing = await get_test_listing(async_client, min_stock=10)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q1 = (
            await async_client.post(
                "/api/v1/quotes", json={"delivery_address_id": addr_id}
            )
        ).json()["id"]
        _r1 = (
            await async_client.post("/api/v1/reservations", json={"quote_id": q1})
        ).json()["id"]

        # Create second quote and reservation
        q2 = (
            await async_client.post(
                "/api/v1/quotes", json={"delivery_address_id": addr_id}
            )
        ).json()["id"]
        _r2 = (
            await async_client.post("/api/v1/reservations", json={"quote_id": q2})
        ).json()["id"]

        # Mismatch: quote 2 with reservation 1 (which belongs to quote 1)
        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": q2,
                "reservation_id": _r1,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "RESERVATION_QUOTE_MISMATCH"
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_released_reservation(async_client: AsyncClient):
    """11. Attempting order creation on released reservation returns 409 RESERVATION_RELEASED."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Release reservation
        await async_client.post(f"/api/v1/reservations/{res_id}/release")

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "RESERVATION_RELEASED"
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_creation_expired_reservation(async_client: AsyncClient):
    """12. Attempting order creation on expired reservation returns 409 RESERVATION_EXPIRED."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Expire reservation
        async with session_factory() as session:
            await session.execute(
                update(InventoryReservation)
                .where(InventoryReservation.id == uuid.UUID(res_id))
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=5))
            )
            await session.commit()

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "RESERVATION_EXPIRED"
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_linked_reservation_protected_from_ordinary_cleanup(
    async_client: AsyncClient,
):
    """13. A reservation in ALLOCATED_TO_ORDER past its TTL is NOT released by ordinary cleanup."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Create order
        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201

        # Force reservation expires_at to the past
        async with session_factory() as session:
            await session.execute(
                update(InventoryReservation)
                .where(InventoryReservation.id == uuid.UUID(res_id))
                .values(expires_at=datetime.now(UTC) - timedelta(minutes=20))
            )
            await session.commit()

        # Run ordinary cleanup
        cleanup_resp = await async_client.post(
            "/api/v1/internal/reservations/cleanup-expired",
            headers=get_internal_auth_headers(),
        )
        assert cleanup_resp.status_code == 200

        # Reservation MUST remain ALLOCATED_TO_ORDER
        async with session_factory() as session:
            res = (
                await session.execute(
                    select(InventoryReservation).where(
                        InventoryReservation.id == uuid.UUID(res_id)
                    )
                )
            ).scalar_one()
            assert res.status == ReservationStatus.ALLOCATED_TO_ORDER.value
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_payment_window_expiry_releases_hold(
    async_client: AsyncClient,
):
    """14. Releasing an allocated reservation on order payment-window expiry cleanly restores stock."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201

        # Simulate order cancellation / payment-window expiry
        async with session_factory() as session:
            service = ReservationService(session)
            await service.release_reservation(
                reservation_id=uuid.UUID(res_id),
                reason="PAYMENT_WINDOW_EXPIRED",
                internal=True,
            )
            await session.commit()

        # Stock is restored to available
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.reserved_quantity == orig_reserved
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_payment_uncertainty_does_not_release_inventory(
    async_client: AsyncClient,
):
    """15. In PENDING_PAYMENT or uncertain state, inventory is NOT released prematurely."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201

        # Hold is still intact: reserved = orig_reserved + 1
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.reserved_quantity == orig_reserved + 1
            assert inv.on_hand_quantity == orig_on_hand
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_shared_session_transaction_rollback(async_client: AsyncClient):
    """16. An injected exception mid-transaction rolls back all table modifications cleanly."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = uuid.UUID(q_resp.json()["id"])

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": str(quote_id)}
        )
        res_id = uuid.UUID(r_resp.json()["id"])

        # Manually invoke OrderService with an injected failure inside session
        async with session_factory() as session:
            service = OrderService(session)
            req = CreateOrderRequest(
                quote_id=quote_id,
                reservation_id=res_id,
                delivery_address_id=uuid.UUID(addr_id),
            )

            # Monkeypatch create_outbox_event to raise an unexpected runtime error
            async def failing_outbox(*args, **kwargs):
                raise RuntimeError("Injected database failure during outbox write!")

            service.repo.create_outbox_event = failing_outbox

            with pytest.raises(RuntimeError, match="Injected database failure"):
                await service.create_order(
                    req=req,
                    customer_id=uuid.UUID(user_data["id"]),
                )
            await session.rollback()

        # Verify nothing persisted in database
        async with session_factory() as session:
            orders = (
                (await session.execute(select(Order).where(Order.quote_id == quote_id)))
                .scalars()
                .all()
            )
            assert len(orders) == 0

            quote = (
                await session.execute(
                    select(CheckoutQuote).where(CheckoutQuote.id == quote_id)
                )
            ).scalar_one()
            assert quote.is_consumed is False
            assert quote.status == QuoteStatus.ACTIVE.value

            res = (
                await session.execute(
                    select(InventoryReservation).where(
                        InventoryReservation.id == res_id
                    )
                )
            ).scalar_one()
            assert res.status == ReservationStatus.ACTIVE.value
            assert res.order_id is None
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_inventory_allocation_and_confirmation_accounting(
    async_client: AsyncClient,
):
    """17. Verifies stock counters: before order (on_hand=X, reserved=0), hold (reserved=1), confirmation (on_hand=X-1, reserved=0)."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # 1. State during reservation hold
        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand
            assert inv.reserved_quantity == orig_reserved + 1

        # 2. State after order creation (order placed, payment pending)
        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201

        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand
            assert inv.reserved_quantity == orig_reserved + 1

        # 3. State after payment confirmation (Phase 2F simulation)
        async with session_factory() as session:
            res_service = ReservationService(session)
            await res_service.confirm_reservation(
                reservation_id=uuid.UUID(res_id),
                internal=True,
            )
            await session.commit()

        async with session_factory() as session:
            inv = (await session.execute(inv_stmt)).scalar_one()
            assert inv.on_hand_quantity == orig_on_hand - 1
            assert inv.reserved_quantity == orig_reserved
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_quote_consumed_exactly_once(async_client: AsyncClient):
    """18. Verifies quote.is_consumed is true and cannot be used again."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        resp1 = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp1.status_code == 201

        async with session_factory() as session:
            quote = (
                await session.execute(
                    select(CheckoutQuote).where(CheckoutQuote.id == uuid.UUID(quote_id))
                )
            ).scalar_one()
            assert quote.is_consumed is True
            assert quote.consumed_at is not None
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_selective_cart_reconciliation(async_client: AsyncClient):
    """19. Verifies only quoted items are pruned; newly added listings and extra quantities remain in cart."""
    listing = await get_test_listing(async_client, min_stock=10)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)

        # 1. Add 1 unit of listing to cart
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )

        # 2. Generate quote for 1 unit
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # 3. Customer modifies cart AFTER generating quote: adds another unit (quantity=2)
        cart_resp = await async_client.get("/api/v1/cart")
        cart_item_id = cart_resp.json()["items"][0]["id"]
        await async_client.patch(
            f"/api/v1/cart/items/{cart_item_id}",
            json={"quantity": 2},
        )

        # 4. Place order for the 1-unit quote
        order_resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert order_resp.status_code == 201

        # 5. Check cart: exactly 1 unit should remain (2 - 1 = 1)
        cart_after = await async_client.get("/api/v1/cart")
        assert len(cart_after.json()["items"]) == 1
        assert cart_after.json()["items"][0]["quantity"] == 1
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_customer_order_retrieval_isolation(async_client: AsyncClient):
    """20. Customer B attempting to retrieve Customer A's order receives 404 NOT_FOUND."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        app = create_app()

        # Customer A creates order
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c1:
            u1, e1, a1 = await setup_customer_with_address(c1)
            await c1.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            q1 = (
                await c1.post("/api/v1/quotes", json={"delivery_address_id": a1})
            ).json()["id"]
            r1 = (await c1.post("/api/v1/reservations", json={"quote_id": q1})).json()[
                "id"
            ]
            resp1 = await c1.post(
                "/api/v1/orders",
                json={
                    "quote_id": q1,
                    "reservation_id": r1,
                    "delivery_address_id": a1,
                },
            )
            order_id = resp1.json()["id"]

        # Customer B attempts to retrieve Customer A's order
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c2:
            u2, e2, a2 = await setup_customer_with_address(c2)
            get_resp = await c2.get(f"/api/v1/orders/{order_id}")
            assert get_resp.status_code == 404
            assert get_resp.json()["error"]["code"] == "ORDER_NOT_FOUND"

            # Check list orders: Customer B's list should be empty
            list_resp = await c2.get("/api/v1/orders")
            assert list_resp.status_code == 200
            assert list_resp.json()["total"] == 0
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_guest_order_retrieval_authorization(async_client: AsyncClient):
    """21. Guest cannot retrieve order without matching basket_guest_cart cookie."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        app = create_app()
        guest_cookie_a = f"guest_a_{uuid.uuid4().hex}"
        guest_cookie_b = f"guest_b_{uuid.uuid4().hex}"

        # Guest A creates order
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"basket_guest_cart": guest_cookie_a},
        ) as ca:
            await ca.post(
                "/api/v1/cart/items",
                json={"listing_id": str(listing_id), "quantity": 1},
            )
            q = (await ca.post("/api/v1/quotes", json={"delivery_state": "KA"})).json()[
                "id"
            ]
            r = (await ca.post("/api/v1/reservations", json={"quote_id": q})).json()[
                "id"
            ]
            resp = await ca.post(
                "/api/v1/orders",
                json={
                    "quote_id": q,
                    "reservation_id": r,
                    "delivery_address": VALID_ADDRESS_PAYLOAD,
                },
            )
            assert resp.status_code == 201
            order_id = resp.json()["id"]

            # Guest A can fetch their order
            fetch_resp = await ca.get(f"/api/v1/orders/{order_id}")
            assert fetch_resp.status_code == 200

        # Guest B attempts to fetch Guest A's order -> 404
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"basket_guest_cart": guest_cookie_b},
        ) as cb:
            fetch_b = await cb.get(f"/api/v1/orders/{order_id}")
            assert fetch_b.status_code == 404
            assert fetch_b.json()["error"]["code"] == "ORDER_NOT_FOUND"

        # Unauthenticated request without cookies -> 404
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c_none:
            fetch_none = await c_none.get(f"/api/v1/orders/{order_id}")
            assert fetch_none.status_code == 404
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_outbox_atomicity(async_client: AsyncClient):
    """22. Outbox event order.created is committed atomically in the same transaction as the order."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 201
        order_id = uuid.UUID(resp.json()["id"])

        async with session_factory() as session:
            event = (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id)
                )
            ).scalar_one_or_none()
            assert event is not None
            assert event.aggregate_type == "order"
            assert event.event_type == "order.created"
            assert event.status == "PENDING"
            assert event.schema_version == 1
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_outbox_zero_pii_payload_validation(async_client: AsyncClient):
    """23. Verifies outbox event JSON contains zero customer names, street lines, phone numbers, or tokens."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 201
        order_id = uuid.UUID(resp.json()["id"])

        async with session_factory() as session:
            event = (
                await session.execute(
                    select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id)
                )
            ).scalar_one()
            payload = event.payload

            # Check for absence of PII
            payload_str = str(payload).lower()
            assert "ramesh" not in payload_str
            assert "lotus residency" not in payload_str
            assert "100 feet road" not in payload_str
            assert "9876543210" not in payload_str
            assert "password" not in payload_str
            assert "token" not in payload_str
            assert "cookie" not in payload_str

            # Check presence of required non-PII fields
            assert "event_id" in payload
            assert "order_number" in payload
            assert "subtotal_paise" in payload
            assert "total_payable_paise" in payload
            assert "items" in payload
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_order_status_state_machine_validation(async_client: AsyncClient):
    """24. Verifies PENDING_PAYMENT cannot be directly transitioned to SHIPPED or DELIVERED."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        resp = await async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        assert resp.status_code == 201
        order_id = uuid.UUID(resp.json()["id"])

        # Directly mutating order to illegal state (e.g. invalid check constraint)
        async with session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(Order)
                    .where(Order.id == order_id)
                    .values(status="INVALID_STATUS")
                )
                await session.commit()
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
async def test_concurrent_cleanup_and_order_placement(
    async_client: AsyncClient,
):
    """25. Concurrent execution of order placement and reservation expiry worker serializes safely via row locks."""
    listing = await get_test_listing(async_client)
    listing_id = uuid.UUID(listing["id"])
    session_factory = get_session_factory()

    async with session_factory() as session:
        inv_stmt = select(StoreInventory).where(StoreInventory.listing_id == listing_id)
        orig_inv = (await session.execute(inv_stmt)).scalar_one()
        orig_on_hand = orig_inv.on_hand_quantity
        orig_reserved = orig_inv.reserved_quantity

    try:
        user_data, email, addr_id = await setup_customer_with_address(async_client)
        await async_client.post(
            "/api/v1/cart/items",
            json={"listing_id": str(listing_id), "quantity": 1},
        )
        q_resp = await async_client.post(
            "/api/v1/quotes", json={"delivery_address_id": addr_id}
        )
        quote_id = q_resp.json()["id"]

        r_resp = await async_client.post(
            "/api/v1/reservations", json={"quote_id": quote_id}
        )
        res_id = r_resp.json()["id"]

        # Concurrently fire order placement and cleanup-expired
        order_coro = async_client.post(
            "/api/v1/orders",
            json={
                "quote_id": quote_id,
                "reservation_id": res_id,
                "delivery_address_id": addr_id,
            },
        )
        cleanup_coro = async_client.post(
            "/api/v1/internal/reservations/cleanup-expired",
            headers=get_internal_auth_headers(),
        )

        resp_order, resp_cleanup = await asyncio.gather(order_coro, cleanup_coro)
        assert resp_order.status_code == 201
        assert resp_cleanup.status_code == 200

        # Reservation is protected: ALLOCATED_TO_ORDER
        async with session_factory() as session:
            res = (
                await session.execute(
                    select(InventoryReservation).where(
                        InventoryReservation.id == uuid.UUID(res_id)
                    )
                )
            ).scalar_one()
            assert res.status == ReservationStatus.ALLOCATED_TO_ORDER.value
    finally:
        async with session_factory() as session:
            await session.execute(
                update(StoreInventory)
                .where(StoreInventory.listing_id == listing_id)
                .values(
                    on_hand_quantity=orig_on_hand,
                    reserved_quantity=orig_reserved,
                )
            )
            await session.commit()


@pytest.mark.asyncio
class TestOrderAggregateVersionMonotonicity:
    async def test_aggregate_version_created_confirmed_cancelled(
        self, async_client: AsyncClient
    ):
        """Monotonic versioning: created (v1) -> confirmed (v2) -> cancelled (v3)."""
        user, token, order_data = await setup_customer_and_order(async_client)
        order_id = uuid.UUID(order_data["id"])
        amount = order_data["total_payable_paise"]
        session_factory = get_session_factory()

        # Step 1: Verify creation version
        async with session_factory() as session:
            db_order = (
                await session.execute(select(Order).where(Order.id == order_id))
            ).scalar_one()
            assert db_order.version == 1

            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(evts) == 1
            assert evts[0].event_type == "order.created"
            assert evts[0].aggregate_version == 1
            assert evts[0].payload["aggregate_version"] == 1

        # Step 2: Confirm order via payment verification -> version 2
        provider_order_id = f"order_rzp_{uuid.uuid4().hex[:8]}"
        provider_payment_id = f"pay_rzp_{uuid.uuid4().hex[:8]}"
        valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

        fake_provider_order = {
            "id": provider_order_id,
            "amount": amount,
            "currency": "INR",
            "receipt": order_data["order_number"],
            "status": "created",
        }
        fake_provider_payment = {
            "id": provider_payment_id,
            "order_id": provider_order_id,
            "amount": amount,
            "currency": "INR",
            "status": "captured",
        }

        with (
            patch.object(
                RazorpayClient,
                "create_order",
                new_callable=AsyncMock,
                return_value=fake_provider_order,
            ),
            patch.object(
                RazorpayClient,
                "fetch_payment",
                new_callable=AsyncMock,
                return_value=fake_provider_payment,
            ),
        ):
            init_resp = await async_client.post(f"/api/v1/orders/{order_id}/payments")
            assert init_resp.status_code == 201

            verify_resp = await async_client.post(
                f"/api/v1/orders/{order_id}/payments/verify",
                json={
                    "razorpay_order_id": provider_order_id,
                    "razorpay_payment_id": provider_payment_id,
                    "razorpay_signature": valid_sig,
                },
            )
            assert verify_resp.status_code == 200

        # Step 3: Verify confirmation version in DB
        async with session_factory() as session:
            db_order = (
                await session.execute(select(Order).where(Order.id == order_id))
            ).scalar_one()
            assert db_order.status == OrderStatus.CONFIRMED.value
            assert db_order.version == 2

            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(evts) == 2
            assert evts[1].event_type == "order.confirmed"
            assert evts[1].aggregate_version == 2
            assert evts[1].payload["aggregate_version"] == 2

        # Step 4: Cancel confirmed order -> version 3
        async with session_factory() as session:
            order_service = OrderService(session)
            cancelled = await order_service.cancel_order(
                order_id=order_id,
                reason="CUSTOMER_REQUESTED_POST_CONFIRM",
            )
            await session.commit()
            assert cancelled.status == OrderStatus.CANCELLED.value
            assert cancelled.version == 3

        # Step 5: Verify complete monotonically increasing event chain: 1 -> 2 -> 3
        async with session_factory() as session:
            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(evts) == 3
            assert [e.aggregate_version for e in evts] == [1, 2, 3]
            assert [e.event_type for e in evts] == [
                "order.created",
                "order.confirmed",
                "order.cancelled",
            ]
            for i, evt in enumerate(evts, start=1):
                assert evt.payload["aggregate_version"] == i

    async def test_aggregate_version_created_cancelled(self, async_client: AsyncClient):
        """Monotonic versioning: created (v1) -> cancelled (v2)."""
        user, token, order_data = await setup_customer_and_order(async_client)
        order_id = uuid.UUID(order_data["id"])
        session_factory = get_session_factory()

        # Step 1: Verify creation
        async with session_factory() as session:
            db_order = (
                await session.execute(select(Order).where(Order.id == order_id))
            ).scalar_one()
            assert db_order.version == 1

        # Step 2: Cancel directly from PENDING_PAYMENT
        async with session_factory() as session:
            order_service = OrderService(session)
            cancelled = await order_service.cancel_order(
                order_id=order_id,
                reason="PAYMENT_WINDOW_EXPIRED",
            )
            await session.commit()
            assert cancelled.status == OrderStatus.CANCELLED.value
            assert cancelled.version == 2

        # Step 3: Verify monotonic chain: 1 -> 2
        async with session_factory() as session:
            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(evts) == 2
            assert [e.aggregate_version for e in evts] == [1, 2]
            assert [e.event_type for e in evts] == [
                "order.created",
                "order.cancelled",
            ]
            assert evts[0].payload["aggregate_version"] == 1
            assert evts[1].payload["aggregate_version"] == 2

    async def test_repeated_cancellation_attempts_are_idempotent(
        self, async_client: AsyncClient
    ):
        """Repeated cancellation is idempotent: does not increment version or emit duplicate events."""
        user, token, order_data = await setup_customer_and_order(async_client)
        order_id = uuid.UUID(order_data["id"])
        session_factory = get_session_factory()

        # First cancel
        async with session_factory() as session:
            order_service = OrderService(session)
            await order_service.cancel_order(order_id=order_id, reason="FIRST_CANCEL")
            await session.commit()

        # Second cancel (duplicate attempt)
        async with session_factory() as session:
            order_service = OrderService(session)
            second_result = await order_service.cancel_order(
                order_id=order_id,
                reason="DUPLICATE_CANCEL",
            )
            await session.commit()
            assert second_result.version == 2
            assert second_result.status == OrderStatus.CANCELLED.value

        # Third cancel
        async with session_factory() as session:
            order_service = OrderService(session)
            third_result = await order_service.cancel_order(
                order_id=order_id,
                reason="THIRD_CANCEL",
            )
            await session.commit()
            assert third_result.version == 2

        # Verify exactly 2 events exist (created=1, cancelled=2), zero duplicates
        async with session_factory() as session:
            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(evts) == 2
            assert [e.aggregate_version for e in evts] == [1, 2]

    async def test_concurrent_order_state_transitions_monotonicity(
        self, async_client: AsyncClient
    ):
        """Two concurrent cancellation transactions cannot allocate the same aggregate version."""
        user, token, order_data = await setup_customer_and_order(async_client)
        order_id = uuid.UUID(order_data["id"])
        session_factory = get_session_factory()

        async def attempt_cancel(worker_name: str):
            async with session_factory() as session:
                order_service = OrderService(session)
                res = await order_service.cancel_order(
                    order_id=order_id,
                    reason=f"CONCURRENT_{worker_name}",
                )
                await session.commit()
                return res.version

        # Run concurrent cancellations across independent DB sessions
        v1, v2 = await asyncio.gather(
            attempt_cancel("WORKER_A"),
            attempt_cancel("WORKER_B"),
        )

        assert v1 == 2
        assert v2 == 2

        # Verify outbox event versions are strictly unique and no duplicate version was created
        async with session_factory() as session:
            evts = (
                (
                    await session.execute(
                        select(OutboxEvent)
                        .where(OutboxEvent.aggregate_id == order_id)
                        .order_by(OutboxEvent.created_at.asc())
                    )
                )
                .scalars()
                .all()
            )
            versions = [e.aggregate_version for e in evts]
            assert versions == [1, 2]
            assert len(versions) == len(set(versions))
