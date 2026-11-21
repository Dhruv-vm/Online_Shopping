"""Final cycle Part 4: authenticated, role-aware live change notices."""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.orders.models import OutboxEvent
from app.modules.realtime.hub import RealtimeHub
from tests.phase3_helpers import make_retailer, make_user, place_order


def _drain(sub):
    out = []
    while not sub.queue.empty():
        out.append(json.loads(sub.queue.get_nowait()))
    return out


@pytest.mark.asyncio
async def test_order_notices_reach_only_the_buyer_and_its_retailer(
    async_client: AsyncClient,
):
    listing, _ = await make_retailer(
        selling_price_paise=30000, original_price_paise=30000
    )
    other_listing, _ = await make_retailer()
    buyer_id, buyer = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=buyer,
        json={"listing_id": listing["id"], "quantity": 1},
    )
    _, order = await place_order(async_client, buyer)

    hub = RealtimeHub()
    me = hub.connect(buyer_id, "customer")
    stranger = hub.connect(uuid.uuid4(), "customer")
    seller = hub.connect(uuid.UUID(listing["retailer_user_id"]), "retailer")
    other_seller = hub.connect(uuid.UUID(other_listing["retailer_user_id"]), "retailer")
    admin = hub.connect(uuid.uuid4(), "admin")

    n = await hub.publish(
        "fulfilment.status_changed",
        "order_fulfilment",
        order["id"],
        {"order_id": order["id"], "status": "PACKED"},
    )
    assert n == 3
    got = _drain(me)
    assert got == [
        {
            "type": "fulfilment.status_changed",
            "entity": "order_fulfilment",
            "id": order["id"],
            "at": got[0]["at"],
        }
    ]  # a notice only: no payload data is forwarded
    assert _drain(seller) and _drain(admin)
    assert _drain(stranger) == [] and _drain(other_seller) == []


@pytest.mark.asyncio
async def test_catalogue_notices_reach_everyone_and_auction_notices_are_scoped(
    async_client: AsyncClient,
):
    hub = RealtimeHub()
    c1 = hub.connect(uuid.uuid4(), "customer")
    r1 = hub.connect(uuid.uuid4(), "retailer")
    assert await hub.publish("price.changed", "listing", uuid.uuid4(), {}) == 2

    pin = "400001"
    base, _ = await make_retailer(service_pincodes=[pin])
    owner_id, owner = await make_user()
    await async_client.post(
        "/api/v1/cart/items",
        headers=owner,
        json={"listing_id": base["id"], "quantity": 1},
    )
    auction = (
        await async_client.post(
            "/api/v1/auctions/start", headers=owner, json={"pincode": pin}
        )
    ).json()
    own = hub.connect(owner_id, "customer")
    _drain(c1), _drain(r1)
    await hub.publish("auction.bid_placed", "basket_auction", auction["id"], {})
    assert _drain(own) and _drain(r1)
    assert _drain(c1) == []  # another customer is not told about this auction


@pytest.mark.asyncio
async def test_new_live_update_events_are_emitted(async_client: AsyncClient):
    """Fulfilment steps, group-buy membership and offers now produce events."""
    listing, rh = await make_retailer(
        selling_price_paise=40000, original_price_paise=50000
    )
    r = await async_client.post(
        "/api/v1/retailer/offers",
        headers=rh,
        json={
            "name": "Live offer",
            "discount_type": "PERCENTAGE",
            "discount_value": 500,
            "listing_id": listing["id"],
            "min_order_paise": 0,
            "is_active": True,
        },
    )
    assert r.status_code == 201, r.text
    camp = (
        await async_client.post(
            "/api/v1/retailer/community-buying/campaigns",
            headers=rh,
            json={
                "min_participants": 2,
                "max_participants": 3,
                "discount_percent": 10,
                "duration_hours": 24,
                "listing_id": listing["id"],
            },
        )
    ).json()
    _, c = await make_user()
    j = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join", headers=c, json={}
    )
    assert j.status_code == 200, j.text
    async with get_session_factory()() as s:
        types = set(
            (
                await s.execute(
                    select(OutboxEvent.event_type).where(
                        OutboxEvent.aggregate_id.in_(
                            [uuid.UUID(r.json()["id"]), uuid.UUID(camp["id"])]
                        )
                    )
                )
            ).scalars()
        )
    assert {"offer.created", "group_buy.member_joined"} <= types


@pytest.mark.asyncio
async def test_stream_requires_authentication(async_client: AsyncClient):
    r = await async_client.get("/api/v1/realtime/stream")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_retailers_are_notified_of_rfqs_and_auctions_in_their_area(
    async_client: AsyncClient,
):
    pin = "411045"
    base, near = await make_retailer(service_pincodes=[pin])
    _, far = await make_retailer(service_pincodes=["110001"])
    _, cust = await make_user()

    rfq = await async_client.post(
        "/api/v1/exchange/requests",
        headers=cust,
        json={
            "title": "Call Priya on 98xxxxxx01 for this",
            "delivery_pincode": pin,
            "items": [{"name": "ceiling fan", "quantity": 2}],
        },
    )
    assert rfq.status_code == 201, rfq.text
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": base["id"], "quantity": 1},
    )
    a = await async_client.post(
        "/api/v1/auctions/start", headers=cust, json={"pincode": pin}
    )
    assert a.status_code in (200, 201), a.text

    near_items = (await async_client.get("/api/v1/notifications", headers=near)).json()[
        "items"
    ]
    far_items = (await async_client.get("/api/v1/notifications", headers=far)).json()[
        "items"
    ]
    types = {n["event_type"] for n in near_items}
    assert {"retailer.rfq_created", "retailer.auction_started"} <= types
    assert not {"retailer.rfq_created", "retailer.auction_started"} & {
        n["event_type"] for n in far_items
    }
    # the customer's free-text title (which here holds a phone number) is never copied
    assert all(
        "Priya" not in n["message"] and "98xx" not in n["message"] for n in near_items
    )
