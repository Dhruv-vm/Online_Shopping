"""Final cycle Part 8: Basket Monthly Essentials — scheduling and safe preparation."""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import get_session_factory
from app.modules.catalogue.models import ProductListing
from app.modules.orders.models import CustomerNotification, Order
from app.modules.payments.models import Payment
from app.modules.recurring.models import RecurringBasket, RecurringBasketRun
from app.modules.recurring.service import next_occurrence, prepare_due_recurring_baskets
from tests.phase3_helpers import make_retailer, make_user


def test_next_occurrence_rules():
    b = RecurringBasket(
        day_of_month=5, start_date=date(2026, 12, 1), end_date=None, skip_dates=[]
    )
    assert next_occurrence(b, date(2026, 11, 21)) == date(2026, 12, 5)
    assert next_occurrence(b, date(2026, 12, 6)) == date(2027, 1, 5)
    b.skip_dates = ["2026-12-05"]
    assert next_occurrence(b, date(2026, 11, 21)) == date(2027, 1, 5)
    b.end_date = date(2026, 12, 31)
    assert next_occurrence(b, date(2026, 11, 21)) is None


async def _basket(client, headers, day, start):
    listing, _ = await make_retailer(
        selling_price_paise=20000, original_price_paise=25000
    )
    await client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"listing_id": listing["id"], "quantity": 3},
    )
    r = await client.post(
        "/api/v1/recurring-baskets",
        headers=headers,
        json={
            "name": "Monthly essentials",
            "day_of_month": day,
            "start_date": start.isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    return listing, r.json()


@pytest.mark.asyncio
async def test_schedule_edit_pause_skip_cancel(async_client: AsyncClient):
    _, cust = await make_user()
    assert (
        await async_client.post(
            "/api/v1/recurring-baskets",
            headers=cust,
            json={"day_of_month": 5, "start_date": "2027-01-01"},
        )
    ).json()["error"]["code"] == "CART_EMPTY"
    listing, b = await _basket(async_client, cust, 5, date(2027, 1, 1))
    assert (
        b["status"] == "ACTIVE"
        and b["next_run_date"] == "2027-01-05"
        and b["autopay"] == "NOT_ENABLED"
    )
    assert (
        b["items"][0]["listing_id"] == listing["id"] and b["items"][0]["quantity"] == 3
    )
    url = f"/api/v1/recurring-baskets/{b['id']}"

    e = (
        await async_client.patch(
            url,
            headers=cust,
            json={
                "day_of_month": 10,
                "end_date": "2027-06-30",
                "quantities": {listing["id"]: 2},
            },
        )
    ).json()
    assert (
        e["next_run_date"] == "2027-01-10"
        and e["end_date"] == "2027-06-30"
        and e["items"][0]["quantity"] == 2
    )
    s = (await async_client.post(f"{url}/skip", headers=cust)).json()
    assert s["next_run_date"] == "2027-02-10" and "2027-01-10" in s["skip_dates"]
    assert s["recent_runs"][0]["status"] == "SKIPPED"
    p = (await async_client.post(f"{url}/pause", headers=cust)).json()
    assert p["status"] == "PAUSED" and p["next_run_date"] is None
    r = (await async_client.post(f"{url}/resume", headers=cust)).json()
    assert r["status"] == "ACTIVE" and r["next_run_date"] == "2027-02-10"
    c = (await async_client.post(f"{url}/cancel", headers=cust)).json()
    assert c["status"] == "CANCELLED" and c["next_run_date"] is None
    assert (await async_client.post(f"{url}/resume", headers=cust)).status_code == 409
    _, other = await make_user()
    assert (await async_client.get(url, headers=other)).status_code == 404


@pytest.mark.asyncio
async def test_preparation_checks_live_data_once_and_never_orders_or_charges(
    async_client: AsyncClient,
):
    cust_id, cust = await make_user()
    today = date.today()
    start = today + timedelta(days=1)
    day = start.day if start.day <= 28 else 28
    listing, b = await _basket(async_client, cust, day, start)
    bid = uuid.UUID(b["id"])
    # Price goes up after set-up: the check must show it.
    async with get_session_factory()() as s:
        lst = await s.get(ProductListing, uuid.UUID(listing["id"]))
        lst.selling_price_paise = 22000
        await s.commit()
        orders_before = (
            await s.execute(select(func.count()).select_from(Order))
        ).scalar()
        pays_before = (
            await s.execute(select(func.count()).select_from(Payment))
        ).scalar()

    chk = (
        await async_client.get(
            f"/api/v1/recurring-baskets/{b['id']}/check", headers=cust
        )
    ).json()
    line = chk["lines"][0]
    assert (
        line["status"] == "PRICE_CHANGED" and line["previous_unit_price_paise"] == 20000
    )
    assert (
        line["current_unit_price_paise"] == 22000 and chk["items_total_paise"] == 66000
    )
    assert any("₹200.00 → ₹220.00" in c for c in chk["changes"])

    if b["next_run_date"] == start.isoformat():
        async with get_session_factory()() as s:
            assert await prepare_due_recurring_baskets(s, today) >= 1
            await s.commit()
        async with (
            get_session_factory()() as s
        ):  # second run: nothing new for that date
            await prepare_due_recurring_baskets(s, today)
            await s.commit()
            runs = (
                (
                    await s.execute(
                        select(RecurringBasketRun).where(
                            RecurringBasketRun.recurring_basket_id == bid
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert [r.status for r in runs] == ["PREPARED"]
            notes = (
                await s.execute(
                    select(func.count())
                    .select_from(CustomerNotification)
                    .where(
                        CustomerNotification.customer_id == cust_id,
                        CustomerNotification.event_type == "RECURRING_BASKET_READY",
                    )
                )
            ).scalar()
            assert notes == 1

    loaded = (
        await async_client.post(
            f"/api/v1/recurring-baskets/{b['id']}/load-to-cart", headers=cust
        )
    ).json()
    assert loaded["loaded"] == 1
    async with get_session_factory()() as s:
        assert (
            await s.execute(select(func.count()).select_from(Order))
        ).scalar() == orders_before
        assert (
            await s.execute(select(func.count()).select_from(Payment))
        ).scalar() == pays_before
