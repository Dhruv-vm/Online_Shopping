"""Final cycle Part 9: secure, expiring WhatsApp invitations for group buys."""

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.community.models import GroupBuyCampaign, GroupBuyInvite
from tests.phase3_helpers import make_user
from tests.test_p3_community_buying import _campaign


@pytest.mark.asyncio
async def test_invite_link_message_validation_and_join(async_client: AsyncClient):
    _, _, camp = await _campaign(async_client)
    sender_id, sender = await make_user()
    r = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/invites",
        headers={**sender, "Origin": "http://10.0.0.5:3100"},
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    token = inv["token"]
    assert inv["url"] == f"http://10.0.0.5:3100/community-buying/invite/{token}"
    assert inv["whatsapp_url"].startswith("https://wa.me/?text=")
    text = unquote(inv["whatsapp_url"].split("text=", 1)[1])
    # campaign facts are present …
    assert camp["title"] in text and "₹300.00" in text and "₹400.00" in text
    assert "0 of" in text and "Invite valid until" in text and "IST" in text
    # … and nothing about the sender
    assert (
        str(sender_id) not in text
        and str(sender_id)[:8] not in text
        and "ref=" not in text
    )
    async with get_session_factory()() as s:
        row = (await s.execute(select(GroupBuyInvite))).scalars().all()
        assert token not in {x.token_hash for x in row}  # only the hash is stored

    # Public preview validates the token; garbage and tampered tokens are rejected.
    p = await async_client.get(f"/api/v1/community-buying/invites/{token}")
    assert p.status_code == 200 and p.json()["can_join"] is True
    assert set(p.json()) >= {
        "group_price_paise",
        "current_participants",
        "invite_expires_at",
    }
    assert (
        await async_client.get("/api/v1/community-buying/invites/not-a-token")
    ).status_code == 404
    assert (
        await async_client.get(f"/api/v1/community-buying/invites/{token}x")
    ).status_code == 404

    # Joining needs a signed-in customer; then it works once like a normal join.
    assert (
        await async_client.post(
            f"/api/v1/community-buying/invites/{token}/join", json={"quantity": 1}
        )
    ).status_code in (401, 403)
    _, friend = await make_user()
    j = await async_client.post(
        f"/api/v1/community-buying/invites/{token}/join",
        headers=friend,
        json={"quantity": 1},
    )
    assert j.status_code == 200, j.text
    assert j.json()["current_participants"] == 1

    # A bad Origin falls back to the configured site address.
    bad = (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/invites",
            headers={**sender, "Origin": "javascript:alert(1)"},
        )
    ).json()
    assert bad["url"].startswith("http") and "javascript" not in bad["url"]


@pytest.mark.asyncio
async def test_expired_invite_and_closed_campaign_cannot_be_used(
    async_client: AsyncClient,
):
    _, _, camp = await _campaign(async_client)
    _, sender = await make_user()
    token = (
        await async_client.post(
            f"/api/v1/community-buying/campaigns/{camp['id']}/invites", headers=sender
        )
    ).json()["token"]
    async with get_session_factory()() as s:
        inv = (
            await s.execute(
                select(GroupBuyInvite).where(
                    GroupBuyInvite.campaign_id == uuid.UUID(camp["id"])
                )
            )
        ).scalar_one()
        inv.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    _, friend = await make_user()
    assert (
        await async_client.get(f"/api/v1/community-buying/invites/{token}")
    ).status_code == 410
    j = await async_client.post(
        f"/api/v1/community-buying/invites/{token}/join",
        headers=friend,
        json={"quantity": 1},
    )
    assert j.status_code == 410 and j.json()["error"]["code"] == "INVITE_EXPIRED"

    async with get_session_factory()() as s:
        c = await s.get(GroupBuyCampaign, uuid.UUID(camp["id"]))
        c.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    r = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/invites", headers=sender
    )
    assert r.status_code == 409
