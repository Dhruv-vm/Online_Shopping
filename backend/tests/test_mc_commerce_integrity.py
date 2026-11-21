"""Marketplace-completion regressions: payment-gated fulfilment, analytics
definitions and discount units."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.orders.models import Order
from tests.phase3_helpers import make_retailer, make_user, place_order


async def _mark_paid(order_id: str) -> None:
    async with get_session_factory()() as session:
        order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        order.status = "CONFIRMED"
        order.payment_status = "SUCCEEDED"
        await session.commit()
    async with get_session_factory()() as session:
        from app.modules.orders.models import OrderItem

        for item in (
            await session.execute(
                select(OrderItem).where(OrderItem.order_id == uuid.UUID(order_id))
            )
        ).scalars():
            item.fulfillment_status = "CONFIRMED"
        await session.commit()


@pytest.mark.asyncio
async def test_unpaid_orders_excluded_from_sales_and_cannot_be_fulfilled(
    async_client: AsyncClient,
):
    listing, r_headers = await make_retailer(
        selling_price_paise=50000, original_price_paise=50000, on_hand_quantity=20
    )
    _, c_headers = await make_user("customer")
    r = await async_client.post(
        "/api/v1/cart/items",
        headers=c_headers,
        json={"listing_id": listing["id"], "quantity": 2},
    )
    assert r.status_code in (200, 201), r.text
    _, order = await place_order(async_client, c_headers)

    a = (await async_client.get("/api/v1/retailer/analytics", headers=r_headers)).json()
    assert a["gross_sales_paise"] == 0
    assert a["paid_orders"] == 0
    assert a["pending_payment_orders"] == 1
    assert a["orders_by_status"].get("PENDING_PAYMENT") == 1

    blocked = await async_client.patch(
        f"/api/v1/retailer/orders/{order['id']}/status",
        headers=r_headers,
        json={"status": "PROCESSING"},
    )
    assert blocked.status_code == 409

    await _mark_paid(order["id"])
    for status in ("PROCESSING", "PACKED", "SHIPPED", "DELIVERED"):
        step = await async_client.patch(
            f"/api/v1/retailer/orders/{order['id']}/status",
            headers=r_headers,
            json={"status": status},
        )
        assert step.status_code == 200, (status, step.text)

    a = (await async_client.get("/api/v1/retailer/analytics", headers=r_headers)).json()
    assert a["paid_orders"] == 1
    assert a["gross_sales_paise"] == 100000
    assert a["settled_revenue_paise"] == 100000
    assert a["fulfilled_orders"] == 1
    assert a["units_dispatched"] == 2
    assert a["average_order_value_paise"] == 100000
    assert a["pending_payment_orders"] == 0


@pytest.mark.asyncio
async def test_retailer_percentage_offer_uses_basis_points(async_client: AsyncClient):
    _, r_headers = await make_retailer(selling_price_paise=50000)
    ok = await async_client.post(
        "/api/v1/retailer/offers",
        headers=r_headers,
        json={
            "name": "Twenty percent",
            "discount_type": "PERCENTAGE",
            "discount_value": 2000,
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["discount_value"] == 2000
    too_big = await async_client.post(
        "/api/v1/retailer/offers",
        headers=r_headers,
        json={"name": "Too big", "discount_type": "PERCENTAGE", "discount_value": 9001},
    )
    assert too_big.status_code == 422
    upd = await async_client.put(
        f"/api/v1/retailer/offers/{ok.json()['id']}",
        headers=r_headers,
        json={"discount_value": 9500},
    )
    assert upd.status_code == 422
