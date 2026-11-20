"""Phase 3F Price Intelligence + Phase 3G Sale Stream."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.orders.models import OutboxEvent
from app.modules.price_intel.models import PriceHistoryTick
from app.modules.price_intel.service import record_price_tick
from app.modules.sale_stream.models import SaleStreamEvent
from tests.phase3_helpers import make_retailer


@pytest.mark.asyncio
async def test_price_change_records_tick_event_and_price_drop(
    async_client: AsyncClient,
):
    listing, headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=120000
    )
    resp = await async_client.patch(
        f"/api/v1/retailer/listings/{listing['id']}",
        headers=headers,
        json={"selling_price_paise": 80000},
    )
    assert resp.status_code == 200, resp.text
    lid = uuid.UUID(listing["id"])
    async with get_session_factory()() as s:
        tick = (
            await s.execute(
                select(PriceHistoryTick).where(PriceHistoryTick.listing_id == lid)
            )
        ).scalar_one()
        assert tick.selling_price_paise == 80000 and tick.mrp_paise == 120000
        ev = (
            await s.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "price.changed",
                    OutboxEvent.aggregate_id == lid,
                )
            )
        ).scalar_one()
        assert ev.payload["previous_price_paise"] == 100000
        drop = (
            await s.execute(
                select(SaleStreamEvent).where(SaleStreamEvent.listing_id == lid)
            )
        ).scalar_one()
        assert drop.event_type == "PRICE_DROP" and drop.flash_price_paise == 80000

    feed = await async_client.get(
        "/api/v1/sale-stream/live", params={"event_type": "PRICE_DROP"}
    )
    assert feed.status_code == 200
    item = next(i for i in feed.json()["items"] if i["listing_id"] == listing["id"])
    assert item["discount_pct"] == 20.0
    assert item["stock_remaining"] == 50
    assert item["seconds_remaining"] > 0


@pytest.mark.asyncio
async def test_small_price_drop_is_not_streamed(async_client: AsyncClient):
    listing, headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=100000
    )
    await async_client.patch(
        f"/api/v1/retailer/listings/{listing['id']}",
        headers=headers,
        json={"selling_price_paise": 98000},
    )
    async with get_session_factory()() as s:
        n = (
            (
                await s.execute(
                    select(SaleStreamEvent).where(
                        SaleStreamEvent.listing_id == uuid.UUID(listing["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
    assert n == []


@pytest.mark.asyncio
async def test_expired_events_never_served(async_client: AsyncClient):
    """Sale Stream Rewind is out of scope: expired events are not retrievable."""
    listing, headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=100000
    )
    await async_client.patch(
        f"/api/v1/retailer/listings/{listing['id']}",
        headers=headers,
        json={"selling_price_paise": 50000},
    )
    async with get_session_factory()() as s:
        ev = (
            await s.execute(
                select(SaleStreamEvent).where(
                    SaleStreamEvent.listing_id == uuid.UUID(listing["id"])
                )
            )
        ).scalar_one()
        ev.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    feed = await async_client.get("/api/v1/sale-stream/live", params={"limit": 50})
    assert all(i["listing_id"] != listing["id"] for i in feed.json()["items"])


@pytest.mark.asyncio
async def test_flash_deal_from_time_limited_offer(async_client: AsyncClient):
    listing, headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=100000
    )
    resp = await async_client.post(
        "/api/v1/retailer/offers",
        headers=headers,
        json={
            "name": "2 hour flash",
            "discount_type": "PERCENTAGE",
            "discount_value": 2500,
            "listing_id": listing["id"],
            "valid_to": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        },
    )
    assert resp.status_code in (200, 201), resp.text
    feed = await async_client.get(
        "/api/v1/sale-stream/live", params={"event_type": "FLASH_DEAL"}
    )
    item = next(i for i in feed.json()["items"] if i["listing_id"] == listing["id"])
    assert item["deal_price_paise"] == 75000


@pytest.mark.asyncio
async def test_price_intelligence_genuine_and_inflated(async_client: AsyncClient):
    sf = get_session_factory()
    genuine, _ = await make_retailer(
        selling_price_paise=80000, original_price_paise=100000
    )
    inflated, _ = await make_retailer(
        selling_price_paise=80000, original_price_paise=150000
    )
    today = datetime.now(UTC).date()
    async with sf() as s:
        for d in range(1, 40):
            day = today - timedelta(days=d)
            await record_price_tick(
                s,
                listing_id=uuid.UUID(genuine["id"]),
                selling_price_paise=100000,
                mrp_paise=100000,
                on=day,
            )
            await record_price_tick(
                s,
                listing_id=uuid.UUID(inflated["id"]),
                selling_price_paise=80000,
                mrp_paise=150000 if d <= 10 else 100000,
                on=day,
            )
        await s.commit()

    g = (
        await async_client.get(f"/api/v1/price-intelligence/listings/{genuine['id']}")
    ).json()
    assert g["badge"] == "GENUINE_DISCOUNT"
    assert g["lowest_price_paise"] == 80000 and g["highest_price_paise"] == 100000
    assert g["average_price_30d_paise"] == 100000
    assert g["is_lowest_in_window"] is True
    assert len(g["history"]) == 39

    i = (
        await async_client.get(f"/api/v1/price-intelligence/listings/{inflated['id']}")
    ).json()
    assert i["badge"] == "MRP_INFLATED"


@pytest.mark.asyncio
async def test_price_intelligence_insufficient_history_and_404(
    async_client: AsyncClient,
):
    listing, _ = await make_retailer()
    r = await async_client.get(f"/api/v1/price-intelligence/listings/{listing['id']}")
    assert r.status_code == 200 and r.json()["badge"] == "INSUFFICIENT_HISTORY"
    missing = await async_client.get(
        f"/api/v1/price-intelligence/listings/{uuid.uuid4()}"
    )
    assert missing.status_code == 404
    bad = await async_client.get(
        f"/api/v1/price-intelligence/listings/{listing['id']}", params={"days": 500}
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_tick_upsert_keeps_day_low():
    listing, _ = await make_retailer()
    lid = uuid.UUID(listing["id"])
    async with get_session_factory()() as s:
        for price in (5000, 3000, 4500):
            await record_price_tick(
                s, listing_id=lid, selling_price_paise=price, mrp_paise=6000
            )
        await s.commit()
        t = (
            await s.execute(
                select(PriceHistoryTick).where(PriceHistoryTick.listing_id == lid)
            )
        ).scalar_one()
    assert (t.selling_price_paise, t.day_low_paise) == (4500, 3000)
