"""Regression tests for vulnerabilities fixed in the 2026-11 stabilisation audit.

Each test pins a confirmed defect so it cannot silently return:
* AUD-SEC-01  fulfilment / return endpoints were unauthenticated
* AUD-SEC-02  customers could self-issue refunds on delivered orders
* AUD-SEC-03  return transitions could be replayed (double restock / refund)
* AUD-SEC-04  X-Forwarded-For spoofing bypassed the login rate limiter
* AUD-SEC-05  CSRF origin check used substring matching
* AUD-SEC-06  media URLs accepted javascript:/data: schemes
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from starlette.requests import Request

from app.core.database import get_session_factory
from app.core.validation import validate_media_url
from app.modules.identity.dependencies import _is_local_dev_origin, get_client_ip
from app.modules.orders.models import Order, OrderStatus, PaymentStatus, ReturnStatus
from tests.test_orders import get_internal_auth_headers, setup_customer_and_order


async def _make_delivered_order(async_client: AsyncClient) -> tuple[uuid.UUID, dict]:
    _user, _token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    async with get_session_factory()() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        order.status = OrderStatus.DELIVERED.value
        order.delivered_at = datetime.now(UTC) - timedelta(days=1)
        order.payment_status = PaymentStatus.SUCCEEDED.value
        await session.commit()
    return order_id, order_data


@pytest.mark.asyncio
async def test_fulfilment_endpoints_reject_anonymous_and_customers(
    async_client: AsyncClient,
):
    """AUD-SEC-01: shipment endpoints require admin or internal service auth."""
    _user, _token, order_data = await setup_customer_and_order(async_client)
    order_id = order_data["id"]
    payload = {
        "carrier_name": "Delhivery",
        "carrier_code": "DELHIVERY",
        "tracking_number": "DEL123456789",
    }

    # Authenticated *customer* (Bearer token set by the helper) -> forbidden
    cust = await async_client.post(f"/api/v1/orders/{order_id}/shipments", json=payload)
    assert cust.status_code == 403

    # Anonymous caller -> unauthenticated
    async_client.headers.pop("Authorization", None)
    async_client.cookies.clear()
    anon = await async_client.post(f"/api/v1/orders/{order_id}/shipments", json=payload)
    assert anon.status_code == 401
    anon_ship = await async_client.patch(
        f"/api/v1/orders/{order_id}/shipments/{uuid.uuid4()}",
        json={"status": "DELIVERED"},
    )
    assert anon_ship.status_code == 401
    anon_ret = await async_client.patch(
        f"/api/v1/returns/{uuid.uuid4()}/status", json={"status": "REFUNDED"}
    )
    assert anon_ret.status_code == 401


@pytest.mark.asyncio
async def test_customer_cannot_self_refund(async_client: AsyncClient):
    """AUD-SEC-02: POST /orders/{id}/refunds is admin / internal only."""
    order_id, _ = await _make_delivered_order(async_client)
    resp = await async_client.post(
        f"/api/v1/orders/{order_id}/refunds",
        json={"amount_paise": 100, "reason": "keep the goods, take the money"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_return_transitions_cannot_be_skipped_or_replayed(
    async_client: AsyncClient,
):
    """AUD-SEC-03: state machine blocks skipping steps and replaying side effects."""
    order_id, order_data = await _make_delivered_order(async_client)
    item_id = order_data["items"][0]["id"]
    ret = await async_client.post(
        f"/api/v1/orders/{order_id}/returns",
        json={
            "reason": "Defective",
            "items": [{"order_item_id": item_id, "quantity": 1}],
        },
    )
    assert ret.status_code == 201
    return_id = ret.json()["id"]
    internal = get_internal_auth_headers()

    # Customer cannot drive the return lifecycle
    forbidden = await async_client.patch(
        f"/api/v1/returns/{return_id}/status", json={"status": "APPROVED"}
    )
    assert forbidden.status_code == 403

    # Cannot jump straight to REFUNDED
    skip = await async_client.patch(
        f"/api/v1/returns/{return_id}/status",
        headers=internal,
        json={"status": ReturnStatus.REFUNDED.value},
    )
    assert skip.status_code == 409
    assert skip.json()["error"]["code"] == "INVALID_RETURN_TRANSITION"

    for step in ("APPROVED", "RECEIVED", "INSPECTED"):
        ok = await async_client.patch(
            f"/api/v1/returns/{return_id}/status",
            headers=internal,
            json={"status": step, "restock_approved": True},
        )
        assert ok.status_code == 200, ok.text

    # Replaying INSPECTED (which restocks) is rejected -> no double restock
    replay = await async_client.patch(
        f"/api/v1/returns/{return_id}/status",
        headers=internal,
        json={"status": "INSPECTED", "restock_approved": True},
    )
    assert replay.status_code == 409

    from types import SimpleNamespace

    from app.modules.payments.service import PaymentService

    with patch.object(
        PaymentService,
        "create_refund",
        new_callable=AsyncMock,
        return_value=SimpleNamespace(refund_id=None),
    ) as refund_mock:
        done = await async_client.patch(
            f"/api/v1/returns/{return_id}/status",
            headers=internal,
            json={"status": "REFUNDED"},
        )
        assert done.status_code == 200
        again = await async_client.patch(
            f"/api/v1/returns/{return_id}/status",
            headers=internal,
            json={"status": "REFUNDED"},
        )
        assert again.status_code == 409
        assert refund_mock.await_count == 1  # money moved exactly once


def _request_with(headers: dict[str, str], peer: str = "10.0.0.5") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 1234),
    }
    return Request(scope)


def test_spoofed_forwarded_for_is_ignored_by_default(monkeypatch):
    """AUD-SEC-04: client IP cannot be chosen by the caller."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 0)
    req = _request_with({"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "10.0.0.5"

    monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)
    req = _request_with({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"})
    assert get_client_ip(req) == "203.0.113.9"


def test_csrf_local_origin_match_is_exact():
    """AUD-SEC-05: look-alike hosts must not pass as localhost."""
    assert _is_local_dev_origin("http://localhost:3000")
    assert _is_local_dev_origin("http://127.0.0.1:3000")
    assert not _is_local_dev_origin("https://localhost.evil.example")
    assert not _is_local_dev_origin("https://127.0.0.1.evil.example")


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "/relative.png",
        "ftp://x/y.png",
    ],
)
def test_media_url_rejects_unsafe_schemes(url):
    """AUD-SEC-06."""
    with pytest.raises(ValueError):
        validate_media_url(url)


def test_media_url_accepts_https():
    assert (
        validate_media_url(" https://cdn.example.com/a.png ")
        == "https://cdn.example.com/a.png"
    )


@pytest.mark.asyncio
async def test_failed_refund_is_not_reported_as_refunded(async_client: AsyncClient):
    """A refund that fails at the payment layer must leave the return in
    REFUND_PENDING (retryable), never REFUNDED."""
    order_id, order_data = await _make_delivered_order(async_client)
    item_id = order_data["items"][0]["id"]
    ret = await async_client.post(
        f"/api/v1/orders/{order_id}/returns",
        json={
            "reason": "Defective",
            "items": [{"order_item_id": item_id, "quantity": 1}],
        },
    )
    return_id = ret.json()["id"]
    internal = get_internal_auth_headers()
    for step in ("APPROVED", "RECEIVED", "INSPECTED"):
        r = await async_client.patch(
            f"/api/v1/returns/{return_id}/status",
            headers=internal,
            json={"status": step},
        )
        assert r.status_code == 200
    # No Razorpay capture exists for this order -> the refund cannot succeed.
    resp = await async_client.patch(
        f"/api/v1/returns/{return_id}/status",
        headers=internal,
        json={"status": "REFUNDED"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == ReturnStatus.REFUND_PENDING.value
