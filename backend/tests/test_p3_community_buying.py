"""Phase 3B Basket Community Buying."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.community.models import GroupBuyCampaign, GroupBuyMember
from app.modules.community.service import settle_expired_campaigns
from app.modules.pricing.models import PriceAward
from tests.phase3_helpers import make_retailer, make_user, place_order

BODY = {
    "min_participants": 2,
    "max_participants": 3,
    "discount_percent": 25,
    "duration_hours": 24,
}


async def _campaign(client, **over):
    listing, rh = await make_retailer(
        selling_price_paise=40000, original_price_paise=50000
    )
    r = await client.post(
        "/api/v1/retailer/community-buying/campaigns",
        headers=rh,
        json={**BODY, "listing_id": listing["id"], **over},
    )
    assert r.status_code == 201, r.text
    return listing, rh, r.json()


@pytest.mark.asyncio
async def test_full_group_buy_to_order_flow(async_client: AsyncClient):
    listing, _, camp = await _campaign(async_client)
    assert camp["group_price_paise"] == 30000 and camp["participants_needed"] == 2
    _, c1 = await make_user()
    _, c2 = await make_user()
    j1 = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join",
        headers=c1,
        json={"quantity": 2},
    )
    assert j1.status_code == 200 and j1.json()["my_membership"]["status"] == "JOINED"
    assert (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/join", headers=c1, json={}
        )
    ).status_code == 409
    await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join",
        headers=c2,
        json={"quantity": 1},
    )

    share = (
        await async_client.get(
            f"/api/v1/community-buying/campaigns/{camp['id']}/share", headers=c1
        )
    ).json()
    # Final cycle: the link is a secure invite token, not the campaign id + user ref.
    assert (
        share["whatsapp_url"].startswith("https://wa.me/?text=")
        and "/community-buying/invite/" in share["url"]
        and "ref=" not in share["url"]
    )

    async with get_session_factory()() as s:
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        c.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    async with get_session_factory()() as s:
        assert await settle_expired_campaigns(s) >= 1
        await s.commit()
    detail = (
        await async_client.get(
            f"/api/v1/community-buying/campaigns/{camp['id']}", headers=c1
        )
    ).json()
    assert (
        detail["status"] == "SUCCESSFUL"
        and detail["my_membership"]["status"] == "AWARDED"
    )

    # Member checks out normally; the quote carries the unlocked group price.
    await async_client.post(
        "/api/v1/cart/items",
        headers=c1,
        json={"listing_id": listing["id"], "quantity": 2},
    )
    quote, order = await place_order(async_client, c1)
    item = next(i for i in quote["items"] if i["listing_id"] == listing["id"])
    assert item["unit_discounted_price_paise"] == 30000
    async with get_session_factory()() as s:
        award = (
            await s.execute(
                select(PriceAward).where(
                    PriceAward.source_id == uuid.UUID(camp["id"]),
                    PriceAward.order_id == uuid.UUID(order["id"]),
                )
            )
        ).scalar_one()
        assert award.status == "USED"
        member = (
            await s.execute(
                select(GroupBuyMember).where(GroupBuyMember.award_id == award.id)
            )
        ).scalar_one()
        assert member.status == "PURCHASED" and str(member.order_id) == order["id"]

    # Single use: a second checkout pays the normal price.
    await async_client.post(
        "/api/v1/cart/items",
        headers=c1,
        json={"listing_id": listing["id"], "quantity": 1},
    )
    from tests.phase3_helpers import quote_cart

    q2, _ = await quote_cart(async_client, c1)
    assert (
        next(i for i in q2["items"] if i["listing_id"] == listing["id"])[
            "unit_discounted_price_paise"
        ]
        == 40000
    )


@pytest.mark.asyncio
async def test_failed_campaign_and_full_campaign_auto_settles(
    async_client: AsyncClient,
):
    _, _, camp = await _campaign(async_client)
    _, c1 = await make_user()
    await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join", headers=c1, json={}
    )
    async with get_session_factory()() as s:
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        c.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    async with get_session_factory()() as s:
        await settle_expired_campaigns(s)
        await s.commit()
        assert (await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))).status == "FAILED"
        awards = (
            (
                await s.execute(
                    select(PriceAward).where(
                        PriceAward.source_id == uuid.UUID(camp["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert awards == []

    _, _, full = await _campaign(async_client, max_participants=2)
    for _ in range(2):
        _, h = await make_user()
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{full['id']}/join", headers=h, json={}
        )
    assert (
        await async_client.get(f"/api/v1/community-buying/campaigns/{full['id']}")
    ).json()["status"] == "SUCCESSFUL"
    _, late = await make_user()
    assert (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{full['id']}/join",
            headers=late,
            json={},
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_rbac_validation_and_ownership(async_client: AsyncClient):
    listing, rh, camp = await _campaign(async_client)
    other_listing, other_rh = await make_retailer()
    _, cust = await make_user()
    _, admin = await make_user("admin")
    # Retailer cannot run a campaign on someone else's listing
    r = await async_client.post(
        "/api/v1/retailer/community-buying/campaigns",
        headers=other_rh,
        json={**BODY, "listing_id": listing["id"]},
    )
    assert r.status_code == 404
    # Customers cannot create; retailers cannot join
    assert (
        await async_client.post(
            "/api/v1/retailer/community-buying/campaigns",
            headers=cust,
            json={**BODY, "listing_id": listing["id"]},
        )
    ).status_code == 403
    assert (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/join", headers=rh, json={}
        )
    ).status_code == 403
    assert (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/join", json={}
        )
    ).status_code == 401
    # Validation
    bad = await async_client.post(
        "/api/v1/retailer/community-buying/campaigns",
        headers=rh,
        json={**BODY, "listing_id": listing["id"], "max_participants": 1},
    )
    assert bad.status_code == 422
    too_many = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join",
        headers=cust,
        json={"quantity": 9},
    )
    assert too_many.status_code == 422
    # Other retailer cannot cancel; admin can
    assert (
        await async_client.post(
            f"/api/v1/retailer/community-buying/campaigns/{camp['id']}/cancel",
            headers=other_rh,
        )
    ).status_code == 404
    ok = await async_client.post(
        f"/api/v1/admin/community-buying/campaigns/{camp['id']}/cancel", headers=admin
    )
    assert ok.status_code == 200 and ok.json()["status"] == "CANCELLED"
    listed = (
        await async_client.get(
            "/api/v1/admin/community-buying/campaigns",
            headers=admin,
            params={"status": "CANCELLED"},
        )
    ).json()
    assert any(i["id"] == camp["id"] for i in listed["items"])
