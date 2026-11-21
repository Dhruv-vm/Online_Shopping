"""End-to-end API journeys A–F for the marketplace-completion work.

Each journey drives the real HTTP API in order, as the frontend does. The only
thing replaced is the Razorpay network call (order creation / payment fetch);
the payment signature is still verified with the configured secret.

A  Customer purchase: browse → cart → quote → reserve → order → pay → fulfil → analytics
B  Retailer onboarding: register (pending) → blocked → documents → admin approve → can sell
C  Admin governance: suspend a customer → sessions revoked, login refused → audit log → reinstate
D  Group buying: retailer publishes terms → customer starts → second customer joins
E  Language preference persists on the account across logins
F  Role isolation: business accounts cannot shop; customers cannot use portals
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.modules.payments.client import RazorpayClient
from tests.phase3_helpers import make_retailer, make_user, place_order

PASSWORD = "Str0ngPass!word"


async def _register_customer(client: AsyncClient, name: str = "Journey Shopper"):
    email = f"journey_{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": name, "phone": "+919876543210"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "customer"
    return email, body["user"], {"Authorization": f"Bearer {body['access_token']}"}


async def _login(client: AsyncClient, email: str):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


async def _pay(client: AsyncClient, headers: dict, order: dict) -> dict:
    provider_order_id = f"order_e2e_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_e2e_{uuid.uuid4().hex[:8]}"
    secret = settings.RAZORPAY_KEY_SECRET.get_secret_value()
    signature = hmac.new(
        secret.encode(), f"{provider_order_id}|{provider_payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    amount = order["total_payable_paise"]
    with (
        patch.object(RazorpayClient, "create_order", new_callable=AsyncMock, return_value={
            "id": provider_order_id, "amount": amount, "currency": "INR",
            "receipt": order["order_number"], "status": "created",
        }),
        patch.object(RazorpayClient, "fetch_payment", new_callable=AsyncMock, return_value={
            "id": provider_payment_id, "order_id": provider_order_id, "amount": amount,
            "currency": "INR", "status": "captured",
        }),
    ):
        init = await client.post(f"/api/v1/orders/{order['id']}/payments", headers=headers)
        assert init.status_code == 201, init.text
        # A forged signature must never confirm the order.
        forged = await client.post(
            f"/api/v1/orders/{order['id']}/payments/verify",
            headers=headers,
            json={"razorpay_order_id": provider_order_id, "razorpay_payment_id": provider_payment_id,
                  "razorpay_signature": "0" * 64},
        )
        assert forged.status_code == 400
        ok = await client.post(
            f"/api/v1/orders/{order['id']}/payments/verify",
            headers=headers,
            json={"razorpay_order_id": provider_order_id, "razorpay_payment_id": provider_payment_id,
                  "razorpay_signature": signature},
        )
        assert ok.status_code == 200, ok.text
        return ok.json()


@pytest.mark.asyncio
async def test_journey_a_customer_purchase_to_delivery(async_client: AsyncClient):
    listing, r_headers = await make_retailer(
        selling_price_paise=45000, original_price_paise=50000, on_hand_quantity=10
    )
    _, _, c_headers = await _register_customer(async_client)

    detail = await async_client.get(f"/api/v1/catalogue/products/{listing['product_id']}")
    assert detail.status_code == 200, detail.text

    add = await async_client.post(
        "/api/v1/cart/items", headers=c_headers, json={"listing_id": listing["id"], "quantity": 2}
    )
    assert add.status_code in (200, 201), add.text
    _, order = await place_order(async_client, c_headers)
    assert order["status"] == "PENDING_PAYMENT"

    # Unpaid orders cannot be fulfilled.
    early = await async_client.patch(
        f"/api/v1/retailer/orders/{order['id']}/status", headers=r_headers, json={"status": "PACKED"}
    )
    assert early.status_code == 409, early.text
    assert early.json()["error"]["code"] in ("ORDER_NOT_PAID", "INVALID_STATUS_TRANSITION")

    paid = await _pay(async_client, c_headers, order)
    assert paid["status"] == "CONFIRMED" and paid["payment_status"] == "SUCCEEDED"

    for step in ("PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"):
        r = await async_client.patch(
            f"/api/v1/retailer/orders/{order['id']}/status", headers=r_headers, json={"status": step}
        )
        assert r.status_code == 200, (step, r.text)
    regress = await async_client.patch(
        f"/api/v1/retailer/orders/{order['id']}/status", headers=r_headers, json={"status": "PACKED"}
    )
    assert regress.status_code == 422

    mine = await async_client.get(f"/api/v1/orders/{order['id']}", headers=c_headers)
    assert mine.status_code == 200 and mine.json()["status"] == "DELIVERED"

    analytics = (await async_client.get("/api/v1/retailer/analytics", headers=r_headers)).json()
    assert analytics["paid_orders"] == 1
    assert analytics["gross_sales_paise"] >= 2 * 45000
    assert analytics["settled_revenue_paise"] >= 2 * 45000
    assert analytics["pending_payment_orders"] == 0


@pytest.mark.asyncio
async def test_journey_b_retailer_onboarding_to_selling(async_client: AsyncClient):
    email = f"e2e_shop_{uuid.uuid4().hex[:8]}@example.com"
    reg = await async_client.post(
        "/api/v1/auth/retailer/register",
        json={"email": email, "password": PASSWORD, "full_name": "Meera Iyer", "phone": "+919822222222",
              "store_name": f"Meera Provisions {uuid.uuid4().hex[:4]}", "state": "TN",
              "business_address": "4 Anna Salai, Chennai 600002"},
    )
    assert reg.status_code == 201, reg.text
    user = reg.json()["user"]
    assert user["verification_status"] == "PENDING"

    # Same common login, backend reports the role.
    login = await _login(async_client, email)
    assert login.status_code == 200 and login.json()["user"]["role"] == "retailer"
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    offer = {"name": "Opening offer", "discount_type": "PERCENTAGE", "discount_value": 1000}
    assert (await async_client.post("/api/v1/retailer/offers", headers=h, json=offer)).status_code == 403

    assert (await async_client.put("/api/v1/retailer/profile", headers=h, json={"gstin": "33ABCDE1234F1Z5"})).status_code == 200
    doc = await async_client.post(
        "/api/v1/retailer/documents", headers=h,
        json={"document_type": "GSTIN_CERTIFICATE", "document_number": "33ABCDE1234F1Z5"},
    )
    assert doc.status_code == 201, doc.text

    _, admin_h = await make_user("admin")
    retailer_id = user["retailer_id"]
    pending = (await async_client.get("/api/v1/admin/retailers?verification_status=PENDING", headers=admin_h)).json()
    items = pending if isinstance(pending, list) else pending.get("items", [])
    assert any(str(i.get("id")) == str(retailer_id) for i in items)

    appr = await async_client.post(
        f"/api/v1/admin/retailers/{retailer_id}/verify", headers=admin_h, json={"status": "VERIFIED"}
    )
    assert appr.status_code == 200, appr.text
    created = await async_client.post("/api/v1/retailer/offers", headers=h, json=offer)
    assert created.status_code == 201, created.text
    assert created.json()["discount_value"] == 1000  # 10% in basis points, not 0


@pytest.mark.asyncio
async def test_journey_c_admin_suspends_and_reinstates_customer(async_client: AsyncClient):
    email, user, c_headers = await _register_customer(async_client, "Suspended Shopper")
    _, admin_h = await make_user("admin")

    sus = await async_client.post(
        f"/api/v1/admin/users/{user['id']}/status", headers=admin_h,
        json={"is_active": False, "reason": "Chargeback investigation"},
    )
    assert sus.status_code == 200 and sus.json()["is_active"] is False
    assert (await async_client.get("/api/v1/users/me", headers=c_headers)).status_code in (401, 403)
    assert (await _login(async_client, email)).status_code in (401, 403)

    logs = (await async_client.get("/api/v1/admin/audit-logs?limit=50", headers=admin_h)).json()
    assert any(user["id"] in (e.get("path") or "") or e.get("target_id") == user["id"] for e in logs["items"])

    back = await async_client.post(
        f"/api/v1/admin/users/{user['id']}/status", headers=admin_h,
        json={"is_active": True, "reason": "Investigation closed"},
    )
    assert back.status_code == 200
    assert (await _login(async_client, email)).status_code == 200


@pytest.mark.asyncio
async def test_journey_d_customer_group_buy(async_client: AsyncClient):
    listing, r_headers = await make_retailer(
        selling_price_paise=20000, original_price_paise=20000, on_hand_quantity=30
    )
    tpl = await async_client.post(
        "/api/v1/retailer/community-buying/templates", headers=r_headers,
        json={"listing_id": listing["id"], "min_participants": 2, "max_participants": 4,
              "discount_percent": 15, "duration_hours": 24, "max_quantity_per_member": 2,
              "max_open_campaigns": 2},
    )
    assert tpl.status_code == 201, tpl.text
    _, _, a = await _register_customer(async_client, "Asha Nair")
    _, _, b = await _register_customer(async_client, "Bilal Khan")

    started = await async_client.post(
        "/api/v1/community-buying/start", headers=a,
        json={"template_id": tpl.json()["id"], "quantity": 1},
    )
    assert started.status_code == 201, started.text
    camp = started.json()
    assert camp["current_participants"] == 1 and camp["group_price_paise"] == 17000

    joined = await async_client.post(
        f"/api/v1/community-buying/campaigns/{camp['id']}/join", headers=b, json={"quantity": 1}
    )
    assert joined.status_code == 200, joined.text
    after = joined.json()
    assert after["current_participants"] == 2
    assert sorted(after["participant_initials"]) == ["A", "B"]


@pytest.mark.asyncio
async def test_journey_e_language_preference_persists(async_client: AsyncClient):
    email, user, headers = await _register_customer(async_client)
    assert user.get("preferred_language", "en") == "en"
    put = await async_client.put("/api/v1/i18n/preference", headers=headers, json={"language": "kn"})
    assert put.status_code == 200, put.text
    again = await _login(async_client, email)
    assert again.json()["user"]["preferred_language"] == "kn"
    me = await async_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {again.json()['access_token']}"}
    )
    assert me.json()["preferred_language"] == "kn"
    bad = await async_client.put("/api/v1/i18n/preference", headers=headers, json={"language": "xx"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_journey_f_role_isolation(async_client: AsyncClient):
    listing, r_headers = await make_retailer(selling_price_paise=10000, on_hand_quantity=5)
    _, admin_h = await make_user("admin")
    _, _, c_headers = await _register_customer(async_client)

    for business in (r_headers, admin_h):
        add = await async_client.post(
            "/api/v1/cart/items", headers=business, json={"listing_id": listing["id"], "quantity": 1}
        )
        assert add.status_code == 403, add.text
        assert add.json()["error"]["code"] == "BUSINESS_ACCOUNT_CANNOT_SHOP"
        quote = await async_client.post("/api/v1/quotes", headers=business, json={})
        assert quote.status_code == 403, quote.text

    assert (await async_client.get("/api/v1/admin/overview", headers=c_headers)).status_code == 403
    assert (await async_client.get("/api/v1/retailer/profile", headers=c_headers)).status_code == 403
    assert (await async_client.get("/api/v1/admin/users", headers=r_headers)).status_code == 403
