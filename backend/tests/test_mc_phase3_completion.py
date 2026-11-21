"""Phase 3 completion: customer-started group buys (3B) and price comparison,
alerts, insights and data quality (3F)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.catalogue.models import StoreInventory
from app.modules.community.models import GroupBuyCampaign, GroupBuyMember
from app.modules.community.service import settle_expired_campaigns
from tests.phase3_helpers import add_listing_for_retailer, make_retailer, make_user


async def _template(client, r_headers, listing_id, **kw):
    body = {
        "listing_id": listing_id,
        "min_participants": 2,
        "max_participants": 3,
        "discount_percent": 10,
        "duration_hours": 24,
        "max_quantity_per_member": 2,
        "max_open_campaigns": 2,
    }
    body.update(kw)
    r = await client.post(
        "/api/v1/retailer/community-buying/templates", headers=r_headers, json=body
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_customer_starts_group_buy_and_friends_join(async_client: AsyncClient):
    listing, r_headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=120000, on_hand_quantity=20
    )
    t = await _template(async_client, r_headers, listing["id"])
    assert t["group_price_paise"] == 90000

    public = (await async_client.get("/api/v1/community-buying/templates")).json()
    assert any(x["id"] == t["id"] for x in public["items"])

    _, a = await make_user("customer")
    _, b = await make_user("customer")
    _, c = await make_user("customer")
    started = await async_client.post(
        "/api/v1/community-buying/start",
        headers=a,
        json={"template_id": t["id"], "quantity": 1},
    )
    assert started.status_code == 201, started.text
    camp = started.json()
    assert camp["started_by_customer"] is True
    assert camp["current_participants"] == 1
    assert camp["participant_initials"] == ["P"]
    assert camp["my_membership"]["status"] == "JOINED"

    again = await async_client.post(
        "/api/v1/community-buying/start",
        headers=a,
        json={"template_id": t["id"], "quantity": 1},
    )
    assert again.status_code == 409

    # Retailers may not start customer group buys.
    denied = await async_client.post(
        "/api/v1/community-buying/start",
        headers=r_headers,
        json={"template_id": t["id"], "quantity": 1},
    )
    assert denied.status_code == 403

    # Quantity above the template limit is rejected.
    too_many = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join",
        headers=b,
        json={"quantity": 3},
    )
    assert too_many.status_code == 422

    for h in (b, c):
        j = await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/join",
            headers=h,
            json={"quantity": 1},
        )
        assert j.status_code == 200, j.text
    final = j.json()
    assert final["status"] == "SUCCESSFUL"
    assert final["current_participants"] == 3
    assert len(final["participant_initials"]) == 3


@pytest.mark.asyncio
async def test_settlement_never_awards_more_than_available_stock(
    async_client: AsyncClient,
):
    listing, r_headers = await make_retailer(
        selling_price_paise=50000, original_price_paise=50000, on_hand_quantity=10
    )
    t = await _template(async_client, r_headers, listing["id"], max_participants=5)
    _, a = await make_user("customer")
    _, b = await make_user("customer")
    camp = (
        await async_client.post(
            "/api/v1/community-buying/start",
            headers=a,
            json={"template_id": t["id"], "quantity": 2},
        )
    ).json()
    j = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join",
        headers=b,
        json={"quantity": 2},
    )
    assert j.status_code == 200, j.text

    async with get_session_factory()() as s:
        inv = (
            await s.execute(
                select(StoreInventory).where(
                    StoreInventory.listing_id == uuid.UUID(listing["id"])
                )
            )
        ).scalar_one()
        inv.on_hand_quantity = 3  # stock sold elsewhere meanwhile
        inv.reserved_quantity = 0
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        c.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await s.commit()
    async with get_session_factory()() as s:
        await settle_expired_campaigns(s)
        await s.commit()
    async with get_session_factory()() as s:
        statuses = sorted(
            m.status
            for m in (
                await s.execute(
                    select(GroupBuyMember).where(
                        GroupBuyMember.campaign_id == uuid.UUID(camp["id"])
                    )
                )
            ).scalars()
        )
    assert statuses == ["AWARDED", "NOT_FULFILLED"]


@pytest.mark.asyncio
async def test_price_comparison_alerts_insights_and_quality(async_client: AsyncClient):
    listing, r_headers = await make_retailer(
        selling_price_paise=100000, original_price_paise=110000, on_hand_quantity=5
    )
    other, _ = await make_retailer(
        selling_price_paise=95000, original_price_paise=110000, on_hand_quantity=5
    )
    # second store sells the SAME variant
    await add_listing_for_retailer(
        other["retailer_id"], listing["variant_id"], selling_price_paise=97000
    )
    cmp_ = (
        await async_client.get(
            f"/api/v1/price-intelligence/variants/{listing['variant_id']}/compare"
        )
    ).json()
    assert [o["selling_price_paise"] for o in cmp_["offers"]] == [97000, 100000]
    assert cmp_["offers"][0]["is_cheapest"] is True
    assert cmp_["price_spread_paise"] == 3000

    uid, cust = await make_user("customer")
    alert = await async_client.post(
        "/api/v1/price-intelligence/alerts",
        headers=cust,
        json={"variant_id": listing["variant_id"], "target_price_paise": 90000},
    )
    assert alert.status_code == 201, alert.text
    assert alert.json()["status"] == "ACTIVE"
    assert alert.json()["current_best_price_paise"] == 97000

    upd = await async_client.put(
        f"/api/v1/retailer/listings/{listing['id']}",
        headers=r_headers,
        json={"selling_price_paise": 89000},
    )
    assert upd.status_code == 200, upd.text
    mine = (
        await async_client.get("/api/v1/price-intelligence/alerts", headers=cust)
    ).json()
    assert mine[0]["status"] == "TRIGGERED"
    assert mine[0]["triggered_price_paise"] == 89000

    insights = (
        await async_client.get("/api/v1/retailer/price-insights", headers=r_headers)
    ).json()
    mine_insight = next(i for i in insights if i["listing_id"] == listing["id"])
    assert mine_insight["competitor_count"] == 1
    assert mine_insight["my_rank"] == 1

    _, admin = await make_user("admin")
    q = await async_client.get(
        "/api/v1/admin/price-intelligence/quality", headers=admin
    )
    assert q.status_code == 200 and q.json()["active_listings"] >= 2
    forbidden = await async_client.get(
        "/api/v1/admin/price-intelligence/quality", headers=cust
    )
    assert forbidden.status_code == 403
