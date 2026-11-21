"""Comprehensive test for two-way Dukaan vs Dukaan live auction and simulation workflow."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.database import get_session_factory
from app.modules.auctions.models import BasketAuction
from tests.phase3_helpers import (
    add_listing_for_retailer,
    make_retailer,
    make_user,
)

PIN = "400001"


async def _end(auction_id: str) -> None:
    async with get_session_factory()() as s:
        a = await s.get(BasketAuction, uuid.UUID(auction_id))
        a.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()


@pytest.mark.asyncio
async def test_dukaan_two_way_simulation_and_genuine_bids(async_client: AsyncClient):
    # Setup 2 competing retailers and 1 customer
    base, _ = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=50000, original_price_paise=60000
    )
    b_own, bh = await make_retailer(service_pincodes=[PIN])
    c_own, ch = await make_retailer(service_pincodes=[PIN])
    await add_listing_for_retailer(
        b_own["retailer_id"], base["variant_id"], selling_price_paise=52000
    )
    await add_listing_for_retailer(
        c_own["retailer_id"], base["variant_id"], selling_price_paise=49000
    )

    _, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 2},
    )

    # 1. Customer starts 90-second auction
    start_resp = await async_client.post(
        "/api/v1/auctions/start", headers=cust, json={"pincode": PIN}
    )
    assert start_resp.status_code == 201, start_resp.text
    auction = start_resp.json()
    aid = auction["id"]
    assert auction["status"] == "ACTIVE"
    assert auction["reference_total_paise"] == 100000

    # 2. Customer refreshes / checks active auction
    active_resp = await async_client.get("/api/v1/auctions/active", headers=cust)
    assert active_resp.status_code == 200
    active = active_resp.json()
    assert active is not None and active["id"] == aid

    # 3. Retailer sees active auction
    live_b = (await async_client.get("/api/v1/retailer/auctions", headers=bh)).json()[
        "items"
    ]
    mine = next((x for x in live_b if x["id"] == aid), None)
    assert mine is not None, "Retailer B must see the active auction"
    assert mine["reference_total_paise"] == 100000

    # 4. Retailer triggers simulation on active auction
    sim_resp = await async_client.post(
        f"/api/v1/retailer/auctions/{aid}/simulate", headers=bh
    )
    assert sim_resp.status_code == 201, sim_resp.text
    sim_bid = sim_resp.json()
    assert sim_bid["is_simulated"] is True
    assert sim_bid["bid_price_paise"] < 100000
    assert "[SIMULATED]" in (sim_bid["warranty_note"] or "")

    # 5. Customer live view immediately reflects the simulated bid
    live_cust = (
        await async_client.get(f"/api/v1/auctions/{aid}/live", headers=cust)
    ).json()
    assert len(live_cust["bids"]) == 1
    assert live_cust["bids"][0]["is_simulated"] is True
    assert live_cust["bids"][0]["bid_price_paise"] == sim_bid["bid_price_paise"]

    # 6. Retailer C places genuine bid
    gen_resp = await async_client.post(
        f"/api/v1/retailer/auctions/{aid}/bid",
        headers=ch,
        json={
            "bid_price_paise": sim_bid["bid_price_paise"] - 2000,
            "delivery_eta_minutes": 20,
        },
    )
    assert gen_resp.status_code == 201
    gen_bid = gen_resp.json()
    assert gen_bid["is_simulated"] is False

    # 7. Customer sees both bids correctly ranked
    live_cust_2 = (
        await async_client.get(f"/api/v1/auctions/{aid}/live", headers=cust)
    ).json()
    assert len(live_cust_2["bids"]) == 2
    assert live_cust_2["bids"][0]["id"] == gen_bid["id"]
    assert live_cust_2["bids"][0]["is_simulated"] is False
    assert live_cust_2["bids"][1]["id"] == sim_bid["id"]
    assert live_cust_2["bids"][1]["is_simulated"] is True

    # 8. Auction ends and customer chooses winning simulated bid safely
    await _end(aid)
    acc_sim = await async_client.post(
        f"/api/v1/auctions/{aid}/accept",
        headers=cust,
        json={"bid_id": sim_bid["id"]},
    )
    assert acc_sim.status_code == 200
    acc_data = acc_sim.json()
    assert acc_data["auction"]["status"] == "AWARDED"
    assert acc_data["auction"]["winning_bid_id"] == sim_bid["id"]
    assert (
        "simulation" in acc_data["message"].lower()
        or "demo" in acc_data["message"].lower()
    )
