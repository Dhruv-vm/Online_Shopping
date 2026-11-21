"""Version 2.0 Phase A1 — basket line replacement used by auctions, RFQs and
List to Basket (regression for the Dukaan vs Dukaan acceptance crash)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session_factory
from app.core.exceptions import AppException
from app.modules.auctions.models import BasketAuction
from app.modules.cart.integration import set_customer_cart_lines
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


async def _cart(client, headers) -> dict[str, int]:
    items = (await client.get("/api/v1/cart", headers=headers)).json()["items"]
    out: dict[str, int] = {}
    for i in items:
        assert i["listing_id"] not in out, "listing appears twice in basket"
        out[i["listing_id"]] = i["quantity"]
    return out


async def _auction_with_bid(client, cust, bidder_headers, price):
    a = await client.post("/api/v1/auctions/start", headers=cust, json={"pincode": PIN})
    assert a.status_code == 201, a.text
    aid = a.json()["id"]
    bid = await client.post(
        f"/api/v1/retailer/auctions/{aid}/bid",
        headers=bidder_headers,
        json={"bid_price_paise": price, "delivery_eta_minutes": 20},
    )
    assert bid.status_code == 201, bid.text
    return aid


@pytest.mark.asyncio
async def test_auction_accept_when_winning_listing_already_in_basket(
    async_client: AsyncClient,
):
    """Reproduces the v1.0 audit defect D1: the basket's own store wins."""
    base, base_h = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=50000, original_price_paise=60000
    )
    _, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 2},
    )
    aid = await _auction_with_bid(async_client, cust, base_h, 90000)
    live = (await async_client.get(f"/api/v1/auctions/{aid}/live", headers=cust)).json()
    await _end(aid)

    acc = await async_client.post(
        f"/api/v1/auctions/{aid}/accept",
        headers=cust,
        json={"bid_id": live["bids"][0]["id"]},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["auction"]["status"] == "AWARDED"
    assert await _cart(async_client, cust) == {base["id"]: 2}

    quote, order = await place_order(async_client, cust)
    (line,) = quote["items"]
    assert line["listing_id"] == base["id"]
    assert line["unit_discounted_price_paise"] == 45000  # 90000 bid over 2 units
    assert order["total_payable_paise"] == quote["total_payable_paise"]


@pytest.mark.asyncio
async def test_auction_accept_other_store_replaces_line_and_keeps_later_items(
    async_client: AsyncClient,
):
    base, _ = await make_retailer(
        service_pincodes=[PIN], selling_price_paise=50000, original_price_paise=60000
    )
    rival, rival_h = await make_retailer(service_pincodes=[PIN])
    rival_listing = await add_listing_for_retailer(
        rival["retailer_id"], base["variant_id"], selling_price_paise=49000
    )
    extra, _ = await make_retailer(service_pincodes=[PIN])
    _, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 2},
    )
    aid = await _auction_with_bid(async_client, cust, rival_h, 90000)
    # Added after the auction started: not part of the auctioned snapshot.
    add = await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": extra["id"], "quantity": 1},
    )
    assert add.status_code in (200, 201), add.text
    live = (await async_client.get(f"/api/v1/auctions/{aid}/live", headers=cust)).json()
    await _end(aid)

    acc = await async_client.post(
        f"/api/v1/auctions/{aid}/accept",
        headers=cust,
        json={"bid_id": live["bids"][0]["id"]},
    )
    assert acc.status_code == 200, acc.text
    assert await _cart(async_client, cust) == {rival_listing: 2, extra["id"]: 1}


@pytest.mark.asyncio
async def test_rfq_accept_when_listing_already_in_basket(async_client: AsyncClient):
    rpin = "560034"
    seller, seller_h = await make_retailer(
        service_pincodes=[rpin], selling_price_paise=60000, original_price_paise=70000
    )
    _, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": seller["id"], "quantity": 1},
    )
    r = await async_client.post(
        "/api/v1/exchange/requests",
        headers=cust,
        json={
            "title": "Overlap check",
            "delivery_pincode": rpin,
            "budget_limit_paise": 500000,
            "items": [{"name": "Rice 5kg", "quantity": 2}],
        },
    )
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    bid = await async_client.post(
        f"/api/v1/retailer/exchange/requests/{rid}/bids",
        headers=seller_h,
        json={
            "lines": [
                {
                    "manifest_index": 0,
                    "listing_id": seller["id"],
                    "unit_price_paise": 45000,
                }
            ],
            "estimated_delivery_hours": 3,
        },
    )
    assert bid.status_code == 201, bid.text
    acc = await async_client.post(
        f"/api/v1/exchange/requests/{rid}/accept-bid",
        headers=cust,
        json={"bid_id": bid.json()["id"]},
    )
    assert acc.status_code == 200, acc.text
    assert await _cart(async_client, cust) == {seller["id"]: 2}
    quote, _ = await place_order(async_client, cust)
    (line,) = quote["items"]
    assert line["unit_discounted_price_paise"] == 45000


@pytest.mark.asyncio
async def test_list_to_basket_when_listing_already_in_basket(
    async_client: AsyncClient,
):
    have, _ = await make_retailer()
    new, _ = await make_retailer()
    _, cust = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": have["id"], "quantity": 1},
    )
    b = await async_client.post(
        "/api/v1/vision/build-cart",
        headers=cust,
        json={
            "items": [
                {"listing_id": have["id"], "quantity": 3},
                # the same new listing twice used to insert two rows → 500
                {"listing_id": new["id"], "quantity": 1},
                {"listing_id": new["id"], "quantity": 2},
            ]
        },
    )
    assert b.status_code == 200, b.text
    cart = await _cart(async_client, cust)
    assert cart[have["id"]] == 3
    assert cart[new["id"]] == 2  # last quantity wins, one row


@pytest.mark.asyncio
async def test_residual_unique_violation_becomes_409(async_client: AsyncClient):
    listing, _ = await make_retailer()
    other, _ = await make_retailer()
    cust_id, _ = await make_user()
    async with get_session_factory()() as session:
        # Create the basket first so the only explicit flush left is the final one.
        await set_customer_cart_lines(session, cust_id, [(uuid.UUID(other["id"]), 1)])
        await session.commit()

        async def _boom():
            raise IntegrityError(
                "INSERT INTO cart_items", {}, Exception("violates uq_cart_listing")
            )

        session.flush = _boom  # type: ignore[method-assign]
        with pytest.raises(AppException) as exc:
            await set_customer_cart_lines(
                session, cust_id, [(uuid.UUID(listing["id"]), 1)]
            )
        assert exc.value.code == "CART_CONFLICT" and exc.value.status_code == 409
        await session.rollback()
