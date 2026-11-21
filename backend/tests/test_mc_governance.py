"""Admin governance: audit trail, user suspension, order visibility, health,
RFQ moderation and honest overview KPIs."""

import pytest
from httpx import AsyncClient

from tests.phase3_helpers import make_retailer, make_user, place_order


@pytest.mark.asyncio
async def test_admin_mutations_are_audited_and_users_can_be_suspended(
    async_client: AsyncClient,
):
    admin_id, admin = await make_user("admin")
    victim_id, victim = await make_user("customer")

    assert (
        await async_client.get("/api/v1/users/me", headers=victim)
    ).status_code == 200
    r = await async_client.post(
        f"/api/v1/admin/users/{victim_id}/status",
        headers=admin,
        json={"is_active": False, "reason": "fraud review"},
    )
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (
        await async_client.get("/api/v1/users/me", headers=victim)
    ).status_code == 403

    self_r = await async_client.post(
        f"/api/v1/admin/users/{admin_id}/status",
        headers=admin,
        json={"is_active": False, "reason": "oops"},
    )
    assert self_r.status_code == 409

    logs = (
        await async_client.get(
            f"/api/v1/admin/audit-logs?entity_id={victim_id}", headers=admin
        )
    ).json()
    assert logs["total"] == 1
    entry = logs["items"][0]
    assert entry["method"] == "POST"
    assert entry["route"].endswith("/admin/users/{user_id}/status")
    # The reason the admin gave is kept with the audit entry.
    assert entry["details"]["action"] == "suspend"
    assert entry["details"]["reason"] == "fraud review"
    assert entry["actor_email"].endswith("@example.com")

    users = (
        await async_client.get(
            "/api/v1/admin/users?include_test_fixtures=true&role=customer&limit=5",
            headers=admin,
        )
    ).json()
    assert users["total"] >= 1
    assert "hashed_password" not in users["items"][0]

    # Non-admins are refused everywhere under governance.
    for path in (
        "/api/v1/admin/users",
        "/api/v1/admin/audit-logs",
        "/api/v1/admin/orders",
    ):
        _, cust = await make_user("customer")
        assert (await async_client.get(path, headers=cust)).status_code == 403


@pytest.mark.asyncio
async def test_admin_orders_health_overview_and_rfq_moderation(
    async_client: AsyncClient,
):
    _, admin = await make_user("admin")
    listing, _ = await make_retailer(
        selling_price_paise=20000, original_price_paise=20000, service_pincodes=[]
    )
    _, cust = await make_user("customer")
    await async_client.post(
        "/api/v1/cart/items",
        headers=cust,
        json={"listing_id": listing["id"], "quantity": 1},
    )
    _, order = await place_order(async_client, cust)
    orders = (
        await async_client.get(
            f"/api/v1/admin/orders?q={order['order_number']}&include_test_fixtures=true",
            headers=admin,
        )
    ).json()
    assert orders["total"] == 1
    assert orders["items"][0]["payment_status"] in ("NOT_INITIATED", "PENDING")
    assert orders["items"][0]["retailer_count"] == 1

    ov = (await async_client.get("/api/v1/admin/overview", headers=admin)).json()
    # unpaid orders never count as revenue
    assert ov["paid_orders"] <= ov["total_orders"]
    assert ov["pending_payment_orders"] >= 1

    health = (
        await async_client.get("/api/v1/admin/system/health", headers=admin)
    ).json()
    names = {c["name"]: c["status"] for c in health["components"]}
    assert names["PostgreSQL"] == "ok"
    assert names["Kafka"] == "not_configured"  # blanked in the test suite
    assert "outbox_pending" in health

    rfq = await async_client.post(
        "/api/v1/exchange/requests",
        headers=cust,
        json={
            "title": "Spam spam spam",
            "delivery_pincode": "560038",
            "items": [{"name": "anything", "quantity": 1}],
        },
    )
    assert rfq.status_code == 201, rfq.text
    mod = await async_client.post(
        f"/api/v1/admin/exchange/requests/{rfq.json()['id']}/cancel",
        headers=admin,
        json={"reason": "Spam / not a genuine request"},
    )
    assert mod.status_code == 200 and mod.json()["status"] == "CANCELLED"
    audit = (
        await async_client.get(
            f"/api/v1/admin/audit-logs?entity_id={rfq.json()['id']}", headers=admin
        )
    ).json()
    assert audit["items"][0]["details"] == {
        "action": "cancel_rfq",
        "reason": "Spam / not a genuine request",
    }
