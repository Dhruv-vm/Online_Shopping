"""Reliability regressions fixed in the 2026-11 stabilisation audit.

* AUD-REL-01  catalogue/inventory changes never produced outbox events, so the
              OpenSearch consumer never saw stock or price changes.
* AUD-REL-02  expired reservations were never released automatically (stock leak).
* AUD-REL-03  PostgreSQL search fallback filtered/paginated in Python, returning
              short pages and a `total` that ignored filters; LIKE wildcards leaked.
* AUD-REL-04  retailers could fulfil unpaid orders.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.background import expire_stale_reservations
from app.core.database import get_session_factory
from app.modules.catalogue.models import ProductListing, ProductVariant, StoreInventory
from app.modules.inventory.models import InventoryReservation
from app.modules.orders.models import OutboxEvent
from app.modules.search.service import escape_like
from tests.factories import get_test_listing


async def _guest_reservation(async_client: AsyncClient, qty: int = 2):
    listing = await get_test_listing(async_client, min_stock=5)
    listing_id = uuid.UUID(listing["id"])
    add = await async_client.post(
        "/api/v1/cart/items", json={"listing_id": str(listing_id), "quantity": qty}
    )
    assert add.status_code == 200
    quote = await async_client.post("/api/v1/quotes", json={})
    assert quote.status_code == 201
    res = await async_client.post(
        "/api/v1/reservations", json={"quote_id": quote.json()["id"]}
    )
    assert res.status_code == 201
    return listing_id, uuid.UUID(res.json()["id"])


async def _product_id_for_listing(session, listing_id: uuid.UUID) -> uuid.UUID:
    return (
        await session.execute(
            select(ProductVariant.product_id)
            .join(ProductListing, ProductListing.variant_id == ProductVariant.id)
            .where(ProductListing.id == listing_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_reservation_emits_product_outbox_event(async_client: AsyncClient):
    """AUD-REL-01: stock changes enqueue product.updated in the same transaction."""
    sf = get_session_factory()
    started = datetime.now(UTC) - timedelta(seconds=1)
    listing_id, _ = await _guest_reservation(async_client)
    async with sf() as session:
        product_id = await _product_id_for_listing(session, listing_id)
        events = (
            (
                await session.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_type == "product",
                        OutboxEvent.aggregate_id == product_id,
                        OutboxEvent.event_type == "product.updated",
                        OutboxEvent.created_at >= started,
                    )
                )
            )
            .scalars()
            .all()
        )
    assert events, "reserving stock must enqueue a product.updated outbox event"
    assert events[0].payload["reason"] == "stock_reserved"
    assert events[0].status == "PENDING"


@pytest.mark.asyncio
async def test_background_worker_releases_expired_reservations(
    async_client: AsyncClient,
):
    """AUD-REL-02: abandoned checkouts no longer hold stock forever."""
    sf = get_session_factory()
    listing_id, reservation_id = await _guest_reservation(async_client, qty=2)
    async with sf() as session:
        reserved_before = (
            await session.execute(
                select(StoreInventory.reserved_quantity).where(
                    StoreInventory.listing_id == listing_id
                )
            )
        ).scalar_one()
        res = await session.get(InventoryReservation, reservation_id)
        res.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    released = await expire_stale_reservations(sf)
    assert released >= 1

    async with sf() as session:
        res = await session.get(InventoryReservation, reservation_id)
        assert res.status == "EXPIRED"
        reserved_after = (
            await session.execute(
                select(StoreInventory.reserved_quantity).where(
                    StoreInventory.listing_id == listing_id
                )
            )
        ).scalar_one()
    assert reserved_after == reserved_before - 2


def test_escape_like_neutralises_wildcards():
    """AUD-REL-03: '%' and '_' in a query are literal, not wildcards."""
    assert escape_like("100%_off") == "100\\%\\_off"
    assert escape_like("a\\b") == "a\\\\b"


@pytest.mark.asyncio
async def test_postgres_fallback_filters_are_applied_in_sql(async_client: AsyncClient):
    """AUD-REL-03: totals honour filters and pages are full and consistent."""
    from app.modules.search.service import SearchService

    sf = get_session_factory()
    async with sf() as session:
        svc = SearchService()
        everything = await svc.search(
            session, q="", page=1, page_size=100, force_fallback=True
        )
        in_stock = await svc.search(
            session,
            q="",
            in_stock_only=True,
            page=1,
            page_size=5,
            force_fallback=True,
        )
        price_capped = await svc.search(
            session,
            q="",
            max_price_paise=1,
            page=1,
            page_size=5,
            force_fallback=True,
        )
        wildcard = await svc.search(
            session, q="%%%", page=1, page_size=5, force_fallback=True
        )
    assert everything.engine == "postgres_fallback"
    # The in-stock page is full whenever enough in-stock products exist
    assert len(in_stock.items) == min(5, in_stock.total)
    assert all(item.is_in_stock for item in in_stock.items)
    assert in_stock.total <= everything.total
    # Nothing costs <= 1 paisa: total must reflect the filter (was unfiltered before)
    assert price_capped.total == 0 and price_capped.items == []
    # A bare wildcard query must not match the whole catalogue
    assert wildcard.total == 0


@pytest.mark.asyncio
async def test_retailer_cannot_fulfil_unpaid_order(async_client: AsyncClient):
    """AUD-REL-04: PENDING_PAYMENT orders cannot be moved into fulfilment."""
    from app.modules.catalogue.models import Retailer
    from app.modules.identity.security import create_access_token
    from app.modules.orders.models import Order, OrderItem
    from tests.test_orders import setup_customer_and_order

    _user, _token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    async_client.headers.pop("Authorization", None)
    async_client.cookies.clear()

    sf = get_session_factory()
    async with sf() as session:
        order = await session.get(Order, order_id)
        assert order.status == "PENDING_PAYMENT"
        retailer_id = (
            (
                await session.execute(
                    select(OrderItem.retailer_id).where(OrderItem.order_id == order_id)
                )
            )
            .scalars()
            .first()
        )
        retailer = await session.get(Retailer, retailer_id)
        if retailer.user_id is None:
            # Attach a portal user so the retailer can authenticate.
            from app.modules.identity.models import User
            from app.modules.identity.security import hash_password

            user = User(
                email=f"aud_ret_{uuid.uuid4().hex[:8]}@example.com",
                hashed_password=hash_password("Password123!"),
                full_name="Audit Retailer",
                role="retailer",
            )
            session.add(user)
            await session.flush()
            retailer.user_id = user.id
        retailer.verification_status = "VERIFIED"
        retailer.is_active = True
        await session.commit()
        token = create_access_token(retailer.user_id, role="retailer")

    resp = await async_client.patch(
        f"/api/v1/retailer/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SHIPPED"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "INVALID_STATUS_TRANSITION"
