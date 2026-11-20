"""Phase 3E Dukaan vs Dukaan (90-second reverse auction)."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.core.database import get_session_factory
from app.modules.auctions.models import BasketAuction
from app.modules.auctions.service import close_ended_auctions
from tests.phase3_helpers import (
    add_listing_for_retailer,
    make_retailer,
    make_user,
    place_order,
)

PIN = "400001"


async def _end(auction_id: str) -> None:
    async with get_session_factory()() as s:
        a = await s.get(BasketAuction, uuid.UUID(auction_id))
        a.ends_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()


async def _setup(client):
    base, _ = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=50000, original_price_paise=60000
    )
    b_own, bh = await make_retailer(service_pincodes=[PIN])
    c_own, ch = await make_retailer(service_pincodes=[PIN])
    b_listing = await add_listing_for_retailer(
        b_own["retailer_id"], base["variant_id"], selling_price_paise=52000
    )
    c_listing = await add_listing_for_retailer(
        c_own["retailer_id"], base["variant_id"], selling_price_paise=49000
    )
    _, cust = await make_user()
    await client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 2},
    )
    return base, (b_own, bh, b_listing), (c_own, ch, c_listing), cust


@pytest.mark.asyncio
async def test_full_reverse_auction(async_client: AsyncClient):
    base, (b, bh, b_listing), (c, ch, c_listing), cust = await _setup(async_client)
    a = await async_client.post(
        "/api/v1/auctions/start", headers=cust, json={"pincode": PIN}
    )
    assert a.status_code == 201, a.text
    auction = a.json()
    assert (
        auction["reference_total_paise"] == 100000
        and 85 <= auction["seconds_remaining"] <= 90
    )
    assert (
        await async_client.post(
            "/api/v1/auctions/start", headers=cust, json={"pincode": PIN}
        )
    ).status_code == 409

    live_b = (await async_client.get("/api/v1/retailer/auctions", headers=bh)).json()[
        "items"
    ]
    mine = next(x for x in live_b if x["id"] == auction["id"])
    assert mine["my_list_total_paise"] == 104000 and mine["bids"] is None

    url = f"/api/v1/retailer/auctions/{auction['id']}/bid"
    assert (
        await async_client.post(
            url,
            headers=bh,
            json={"bid_price_paise": 105000, "delivery_eta_minutes": 30},
        )
    ).status_code == 422
    assert (
        await async_client.post(
            url,
            headers=bh,
            json={
                "bid_price_paise": 95000,
                "delivery_eta_minutes": 15,
                "warranty_note": "7-day replacement",
            },
        )
    ).status_code == 201
    assert (
        await async_client.post(
            url, headers=bh, json={"bid_price_paise": 95000, "delivery_eta_minutes": 15}
        )
    ).json()["error"]["code"] == "BID_NOT_LOWER"
    assert (
        await async_client.post(
            url, headers=ch, json={"bid_price_paise": 90000, "delivery_eta_minutes": 45}
        )
    ).status_code == 201
    assert (
        await async_client.post(
            url, headers=bh, json={"bid_price_paise": 92000, "delivery_eta_minutes": 15}
        )
    ).status_code == 201

    live = (
        await async_client.get(f"/api/v1/auctions/{auction['id']}/live", headers=cust)
    ).json()
    assert [x["bid_price_paise"] for x in live["bids"]] == [
        90000,
        92000,
    ]  # best per store
    assert live["bids"][0]["savings_paise"] == 10000

    winner = live["bids"][0]["id"]
    assert (
        await async_client.post(
            f"/api/v1/auctions/{auction['id']}/accept",
            headers=cust,
            json={"bid_id": winner},
        )
    ).json()["error"]["code"] == "AUCTION_STILL_LIVE"
    await _end(auction["id"])
    assert (
        await async_client.post(
            url, headers=bh, json={"bid_price_paise": 80000, "delivery_eta_minutes": 15}
        )
    ).status_code == 409

    acc = await async_client.post(
        f"/api/v1/auctions/{auction['id']}/accept",
        headers=cust,
        json={"bid_id": winner},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["auction"]["status"] == "AWARDED"
    cart = (await async_client.get("/api/v1/cart", headers=cust)).json()
    assert {i["listing_id"] for i in cart["items"]} == {c_listing}

    quote, order = await place_order(async_client, cust)
    line = quote["items"][0]
    assert (
        line["listing_id"] == c_listing and line["unit_discounted_price_paise"] == 45000
    )


@pytest.mark.asyncio
async def test_eligibility_sse_and_rbac(async_client: AsyncClient):
    base, (b, bh, _), _, cust = await _setup(async_client)
    stranger, sh = await make_retailer(
        service_pincodes=[PIN]
    )  # does not stock the variant
    far, fh = await make_retailer(service_pincodes=["110001"])
    await add_listing_for_retailer(
        far["retailer_id"], base["variant_id"], selling_price_paise=40000
    )
    auction = (
        await async_client.post(
            "/api/v1/auctions/start", headers=cust, json={"pincode": PIN}
        )
    ).json()

    assert auction["id"] not in {
        x["id"]
        for x in (
            await async_client.get("/api/v1/retailer/auctions", headers=sh)
        ).json()["items"]
    }
    url = f"/api/v1/retailer/auctions/{auction['id']}/bid"
    assert (
        await async_client.post(
            url, headers=sh, json={"bid_price_paise": 1000, "delivery_eta_minutes": 20}
        )
    ).json()["error"]["code"] == "CANNOT_FULFIL_BASKET"
    assert (
        await async_client.post(
            url, headers=fh, json={"bid_price_paise": 1000, "delivery_eta_minutes": 20}
        )
    ).status_code == 403
    assert (
        await async_client.post(
            url,
            headers=cust,
            json={"bid_price_paise": 1000, "delivery_eta_minutes": 20},
        )
    ).status_code == 403

    _, other = await make_user()
    assert (
        await async_client.get(f"/api/v1/auctions/{auction['id']}/live", headers=other)
    ).status_code == 404
    assert (
        await async_client.post(
            "/api/v1/auctions/start", headers=bh, json={"pincode": PIN}
        )
    ).status_code == 403
    assert (
        await async_client.post(
            "/api/v1/auctions/start", headers=other, json={"pincode": PIN}
        )
    ).status_code == 400
    assert (
        await async_client.post(
            "/api/v1/auctions/start", headers=cust, json={"pincode": "12345"}
        )
    ).status_code == 422

    await _end(auction["id"])
    async with get_session_factory()() as s:
        await close_ended_auctions(s)
        await s.commit()
    async with async_client.stream(
        "GET",
        f"/api/v1/auctions/{auction['id']}/live",
        headers={**cust, "Accept": "text/event-stream"},
    ) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        body = (await r.aread()).decode()
    first = body.split("data: ", 1)[1].split("\n", 1)[0]
    assert json.loads(first)["status"] == "NO_BIDS" and "event: end" in body

    _, admin = await make_user("admin")
    adm = (
        await async_client.get(
            "/api/v1/admin/auctions", headers=admin, params={"status": "NO_BIDS"}
        )
    ).json()
    assert any(x["id"] == auction["id"] for x in adm["items"])
