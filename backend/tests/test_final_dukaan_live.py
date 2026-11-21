"""Final cycle Part 5: what competing stores see during and after a live auction."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.database import get_session_factory
from app.modules.auctions.models import BasketAuction
from app.modules.auctions.service import AuctionService, close_ended_auctions
from app.modules.orders.models import CustomerNotification, OutboxEvent
from tests.test_p3_dukaan_vs_dukaan import PIN, _end, _setup


async def _live(client, headers, auction_id):
    items = (await client.get("/api/v1/retailer/auctions", headers=headers)).json()[
        "items"
    ]
    return next(x for x in items if x["id"] == auction_id)


@pytest.mark.asyncio
async def test_competing_stores_see_position_outbid_and_outcome(
    async_client: AsyncClient,
):
    base, (b, bh, _), (c, ch, _), cust = await _setup(async_client)
    auction = (
        await async_client.post(
            "/api/v1/auctions/start", headers=cust, json={"pincode": PIN}
        )
    ).json()
    aid = auction["id"]
    url = f"/api/v1/retailer/auctions/{aid}/bid"

    # Both eligible stores see the same auction, items, quantity and service area.
    vb, vc = await _live(async_client, bh, aid), await _live(async_client, ch, aid)
    assert vb["pincode"] == vc["pincode"] == PIN
    assert vb["items"] == vc["items"] and vb["items"][0]["quantity"] == 2
    assert (
        vb["competing_stores"] == 0 and vb["my_rank"] is None and vb["outbid"] is False
    )

    await async_client.post(
        url, headers=bh, json={"bid_price_paise": 95000, "delivery_eta_minutes": 15}
    )
    vb = await _live(async_client, bh, aid)
    assert vb["is_winning"] and vb["my_rank"] == 1 and not vb["outbid"]

    await async_client.post(
        url, headers=ch, json={"bid_price_paise": 90000, "delivery_eta_minutes": 45}
    )
    vb, vc = await _live(async_client, bh, aid), await _live(async_client, ch, aid)
    assert vb["outbid"] and vb["my_rank"] == 2 and vb["best_bid_paise"] == 90000
    assert vc["is_winning"] and vc["competing_stores"] == 2
    # The price ladder is visible, but never which store placed a bid.
    assert [(x["price_paise"], x["mine"]) for x in vb["bid_ladder"]] == [
        (95000, True),
        (90000, False),
    ]
    assert all(set(x) == {"price_paise", "at", "mine"} for x in vb["bid_ladder"])
    assert vb["bids"] is None  # store names stay hidden from competitors

    await _end(aid)
    # Two closers racing (the job and a view) emit one close event and one notice each.
    async with get_session_factory()() as s:
        await close_ended_auctions(s)
        await s.commit()
    async with get_session_factory()() as s:
        await AuctionService(s)._close_if_ended(
            await s.get(BasketAuction, uuid.UUID(aid))
        )
        await s.commit()
        closed = (
            await s.execute(
                select(func.count())
                .select_from(OutboxEvent)
                .where(
                    OutboxEvent.event_type == "auction.closed",
                    OutboxEvent.aggregate_id == uuid.UUID(aid),
                )
            )
        ).scalar()
        notices = (
            await s.execute(
                select(func.count())
                .select_from(CustomerNotification)
                .where(
                    CustomerNotification.event_type == "retailer.auction_closed",
                    CustomerNotification.customer_id.in_(
                        [
                            uuid.UUID(b["retailer_user_id"]),
                            uuid.UUID(c["retailer_user_id"]),
                        ]
                    ),
                )
            )
        ).scalar()
    assert closed == 1
    assert notices == 2  # one per bidding store

    rb = (
        await async_client.get("/api/v1/retailer/auctions/recent", headers=bh)
    ).json()["items"]
    assert next(x for x in rb if x["id"] == aid)["my_outcome"] == "AWAITING_CHOICE"

    live = (await async_client.get(f"/api/v1/auctions/{aid}/live", headers=cust)).json()
    winner = live["bids"][0]["id"]  # customer picks the cheapest (store C)
    acc = await async_client.post(
        f"/api/v1/auctions/{aid}/accept", headers=cust, json={"bid_id": winner}
    )
    assert acc.status_code == 200, acc.text

    rb = (
        await async_client.get("/api/v1/retailer/auctions/recent", headers=bh)
    ).json()["items"]
    rc = (
        await async_client.get("/api/v1/retailer/auctions/recent", headers=ch)
    ).json()["items"]
    assert next(x for x in rb if x["id"] == aid)["my_outcome"] == "NOT_SELECTED"
    assert next(x for x in rc if x["id"] == aid)["my_outcome"] == "WON"
    won = (await async_client.get("/api/v1/notifications", headers=ch)).json()["items"]
    assert [n["event_type"] for n in won].count("retailer.auction_won") == 1
