"""Phase 3A Demand Gap & Unmet Demand Aggregation."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import StoreInventory
from app.modules.orders.models import CustomerNotification, OutboxEvent
from tests.phase3_helpers import make_retailer, make_user


def _name() -> str:
    return f"Kashmiri Kahwa Tea {uuid.uuid4().hex[:6]}"


@pytest.mark.asyncio
async def test_signals_aggregate_dedupe_and_count_unique_users(
    async_client: AsyncClient,
):
    name = _name()
    _, c1 = await make_user()
    _, c2 = await make_user()
    body = {"query_text": name, "pincode": "560001"}
    r1 = await async_client.post("/api/v1/demand/signal", json=body, headers=c1)
    assert r1.status_code == 201, r1.text
    pool_id = r1.json()["pool"]["id"]
    r1b = await async_client.post("/api/v1/demand/signal", json=body, headers=c1)
    assert r1b.json()["deduplicated"] is True
    r2 = await async_client.post(
        "/api/v1/demand/signal",
        json={**body, "query_text": name.upper() + "!!"},
        headers=c2,
    )
    p = r2.json()["pool"]
    assert p["id"] == pool_id
    assert (p["unique_users_count"], p["total_demand_count"]) == (2, 2)
    async with get_session_factory()() as s:
        ev = (
            (
                await s.execute(
                    select(OutboxEvent).where(
                        OutboxEvent.aggregate_id == uuid.UUID(pool_id),
                        OutboxEvent.event_type == "demand.pool_threshold_reached",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(ev) == 1


@pytest.mark.asyncio
async def test_regional_language_request_joins_english_pool(async_client: AsyncClient):
    pin = "411001"
    _, c1 = await make_user()
    _, c2 = await make_user()
    a = await async_client.post(
        "/api/v1/demand/signal", json={"query_text": "milk", "pincode": pin}, headers=c1
    )
    b = await async_client.post(
        "/api/v1/demand/signal", json={"query_text": "दूध", "pincode": pin}, headers=c2
    )
    assert a.json()["pool"]["id"] == b.json()["pool"]["id"]


@pytest.mark.asyncio
async def test_retailer_visibility_threshold_pincode_and_fulfilment(
    async_client: AsyncClient,
):
    name = _name()
    pin = "110001"
    near, near_h = await make_retailer(service_pincodes=[pin])
    far, far_h = await make_retailer(service_pincodes=["600001"])
    c1_id, c1 = await make_user()
    _, c2 = await make_user()

    r = await async_client.post(
        "/api/v1/demand/signal", json={"query_text": name, "pincode": pin}, headers=c1
    )
    pool_id = r.json()["pool"]["id"]
    # Below threshold (default 2 unique users): hidden from retailers
    lst = (
        await async_client.get("/api/v1/retailer/demand-gaps", headers=near_h)
    ).json()
    assert pool_id not in {i["id"] for i in lst["items"]}
    await async_client.post(f"/api/v1/demand/pools/{pool_id}/join", json={}, headers=c2)

    near_items = (
        await async_client.get("/api/v1/retailer/demand-gaps", headers=near_h)
    ).json()["items"]
    assert pool_id in {i["id"] for i in near_items}
    far_items = (
        await async_client.get("/api/v1/retailer/demand-gaps", headers=far_h)
    ).json()["items"]
    assert pool_id not in {i["id"] for i in far_items}

    denied = await async_client.post(
        f"/api/v1/retailer/demand-gaps/{pool_id}/fulfill",
        json={"listing_id": far["id"]},
        headers=far_h,
    )
    assert denied.status_code == 403
    foreign = await async_client.post(
        f"/api/v1/retailer/demand-gaps/{pool_id}/fulfill",
        json={"listing_id": far["id"]},
        headers=near_h,
    )
    assert foreign.status_code == 404  # not this retailer's listing
    ok = await async_client.post(
        f"/api/v1/retailer/demand-gaps/{pool_id}/fulfill",
        json={"listing_id": near["id"], "note": "Stocked"},
        headers=near_h,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "FULFILLED" and ok.json()["responded_by_me"] is True
    dup = await async_client.post(
        f"/api/v1/retailer/demand-gaps/{pool_id}/fulfill",
        json={"listing_id": near["id"]},
        headers=near_h,
    )
    assert dup.status_code == 409

    mine = (await async_client.get("/api/v1/demand/my-requests", headers=c1)).json()[
        "items"
    ]
    offer = next(p for p in mine if p["id"] == pool_id)["offers"][0]
    assert offer["listing_id"] == near["id"]
    async with get_session_factory()() as s:
        n = (
            (
                await s.execute(
                    select(CustomerNotification).where(
                        CustomerNotification.customer_id == c1_id,
                        CustomerNotification.event_type == "DEMAND_FULFILLED",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert n


@pytest.mark.asyncio
async def test_out_of_stock_signal_validates_stock(async_client: AsyncClient):
    listing, _ = await make_retailer()
    _, c = await make_user()
    body = {"listing_id": listing["id"], "signal_type": "OUT_OF_STOCK"}
    assert (
        await async_client.post("/api/v1/demand/signal", json=body, headers=c)
    ).status_code == 409
    async with get_session_factory()() as s:
        inv = (
            await s.execute(
                select(StoreInventory).where(
                    StoreInventory.listing_id == uuid.UUID(listing["id"])
                )
            )
        ).scalar_one()
        inv.on_hand_quantity = 0
        await s.commit()
    r = await async_client.post("/api/v1/demand/signal", json=body, headers=c)
    assert (
        r.status_code == 201
        and r.json()["pool"]["display_name"] == listing["product_name"]
    )


@pytest.mark.asyncio
async def test_zero_result_search_records_demand(async_client: AsyncClient):
    term = f"unobtainium{uuid.uuid4().hex[:6]}"
    r = await async_client.get(
        "/api/v1/search", params={"q": term, "force_fallback": True}
    )
    assert r.status_code == 200 and r.json()["total"] == 0
    pools = (await async_client.get("/api/v1/demand/pools", params={"q": term})).json()[
        "items"
    ]
    assert len(pools) == 1 and pools[0]["total_demand_count"] == 1
    assert pools[0]["unique_users_count"] == 0  # anonymous signals are not unique users


@pytest.mark.asyncio
async def test_validation_and_rbac(async_client: AsyncClient):
    _, c = await make_user()
    _, admin = await make_user("admin")
    assert (
        await async_client.post("/api/v1/demand/signal", json={}, headers=c)
    ).status_code == 422
    assert (
        await async_client.post(
            "/api/v1/demand/signal",
            json={"query_text": "rice", "pincode": "12"},
            headers=c,
        )
    ).status_code == 422
    assert (
        await async_client.get("/api/v1/retailer/demand-gaps", headers=c)
    ).status_code == 403
    assert (
        await async_client.get("/api/v1/admin/demand/pools", headers=c)
    ).status_code == 403
    assert (await async_client.get("/api/v1/demand/my-requests")).status_code == 401

    r = await async_client.post(
        "/api/v1/demand/signal", json={"query_text": _name()}, headers=c
    )
    pid = r.json()["pool"]["id"]
    upd = await async_client.patch(
        f"/api/v1/admin/demand/pools/{pid}",
        json={"visibility_threshold": 1, "status": "EXPIRED"},
        headers=admin,
    )
    assert upd.status_code == 200 and upd.json()["status"] == "EXPIRED"
    join = await async_client.post(
        f"/api/v1/demand/pools/{pid}/join", json={}, headers=c
    )
    assert join.status_code == 404
    trends = await async_client.get("/api/v1/admin/demand/trends", headers=admin)
    assert trends.status_code == 200 and trends.json()["daily"]
