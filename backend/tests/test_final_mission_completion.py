"""Final cycle Part 10: Basket Mission completion is verified by the backend."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import get_session_factory
from app.modules.missions.completion import complete_missions_for_order
from app.modules.orders.models import CustomerNotification, Order
from tests.phase3_helpers import make_retailer, make_user, place_order

MISSION = {
    "title": "Kitchen set-up",
    "description": "Cookware and grocery staples",
    "budget_paise": 1500000,
    "people_count": 2,
    "preferences": ["stainless steel"],
}


async def _paid(order_id: str) -> None:
    async with get_session_factory()() as s:
        o = await s.get(Order, uuid.UUID(order_id))
        o.payment_status = "SUCCEEDED"
        await s.commit()


async def _complete(order_id: str) -> int:
    async with get_session_factory()() as s:
        o = (
            await s.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.id == uuid.UUID(order_id))
            )
        ).scalar_one()
        n = await complete_missions_for_order(s, o)
        await s.commit()
        return n


@pytest.mark.asyncio
async def test_customer_cannot_self_complete(async_client: AsyncClient):
    _, cust = await make_user()
    m = (await async_client.post("/api/v1/missions", headers=cust, json=MISSION)).json()
    r = await async_client.patch(
        f"/api/v1/missions/{m['id']}", headers=cust, json={"status": "COMPLETED"}
    )
    assert r.status_code == 422  # only the backend sets COMPLETED


@pytest.mark.asyncio
async def test_paid_order_with_all_items_completes_once(async_client: AsyncClient):
    cust_id, cust = await make_user()
    m = (await async_client.post("/api/v1/missions", headers=cust, json=MISSION)).json()
    assert m["purchased_items_count"] == 0 and m["completed_at"] is None
    selected = [i for i in m["items"] if i["is_selected"]]
    # Keep it small: deselect all but two items.
    for it in selected[2:]:
        await async_client.patch(
            f"/api/v1/missions/{m['id']}/items/{it['id']}",
            headers=cust,
            json={"is_selected": False},
        )
    added = (
        await async_client.post(f"/api/v1/missions/{m['id']}/add-to-cart", headers=cust)
    ).json()
    assert added["added_items_count"] == min(2, len(selected))
    detail = (
        await async_client.get(f"/api/v1/missions/{m['id']}", headers=cust)
    ).json()
    assert detail["carted_at"] is not None

    _, order = await place_order(async_client, cust)
    # Unpaid order: nothing completes.
    assert await _complete(order["id"]) == 0
    await _paid(order["id"])
    assert await _complete(order["id"]) == 1
    assert await _complete(order["id"]) == 0  # never twice

    done = (await async_client.get(f"/api/v1/missions/{m['id']}", headers=cust)).json()
    assert done["status"] == "COMPLETED" and done["completed_order_id"] == order["id"]
    assert done["purchased_items_count"] == done["items_count"]
    listed = (await async_client.get("/api/v1/missions", headers=cust)).json()
    entry = next(
        x
        for x in (listed["items"] if isinstance(listed, dict) else listed)
        if x["id"] == m["id"]
    )
    assert entry["status"] == "COMPLETED"
    assert (
        await async_client.patch(
            f"/api/v1/missions/{m['id']}", headers=cust, json={"status": "ACTIVE"}
        )
    ).status_code == 409
    assert (
        await async_client.patch(
            f"/api/v1/missions/{m['id']}", headers=cust, json={"status": "ARCHIVED"}
        )
    ).status_code == 200
    async with get_session_factory()() as s:
        n = (
            await s.execute(
                select(func.count())
                .select_from(CustomerNotification)
                .where(
                    CustomerNotification.customer_id == cust_id,
                    CustomerNotification.event_type == "MISSION_COMPLETED",
                )
            )
        ).scalar()
    assert n == 1


@pytest.mark.asyncio
async def test_order_missing_an_item_does_not_complete(async_client: AsyncClient):
    _, cust = await make_user()
    m = (await async_client.post("/api/v1/missions", headers=cust, json=MISSION)).json()
    extra, _ = await make_retailer(
        selling_price_paise=15000, original_price_paise=15000
    )
    r = await async_client.post(
        f"/api/v1/missions/{m['id']}/items",
        headers=cust,
        json={"listing_id": extra["id"], "quantity": 1},
    )
    assert r.status_code in (200, 201), r.text
    m = r.json()
    selected = [i for i in m["items"] if i["is_selected"]]
    assert len(selected) >= 2
    keep = [i for i in selected if i["listing_id"] == extra["id"]] + [
        i for i in selected if i["listing_id"] != extra["id"]
    ][:1]
    for it in [i for i in selected if i not in keep]:
        await async_client.patch(
            f"/api/v1/missions/{m['id']}/items/{it['id']}",
            headers=cust,
            json={"is_selected": False},
        )
    await async_client.post(f"/api/v1/missions/{m['id']}/add-to-cart", headers=cust)
    cart = (await async_client.get("/api/v1/cart", headers=cust)).json()
    # Remove one mission item from the cart before ordering.
    await async_client.delete(
        f"/api/v1/cart/items/{cart['items'][0]['id']}", headers=cust
    )
    _, order = await place_order(async_client, cust)
    await _paid(order["id"])
    assert await _complete(order["id"]) == 0
    still = (await async_client.get(f"/api/v1/missions/{m['id']}", headers=cust)).json()
    assert still["status"] == "ACTIVE" and still["purchased_items_count"] == 1
