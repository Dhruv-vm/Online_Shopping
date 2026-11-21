"""Version 2.0 Phase A2 — payment initiation must not create a second Razorpay
order when "Pay" is pressed again (v1.0 audit defect D4)."""

import asyncio
import uuid
from itertools import count
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.database import get_session_factory
from app.modules.payments.client import RazorpayClient
from app.modules.payments.models import Payment, PaymentAttemptStatus
from tests.test_payments import setup_customer_and_order


def _fake_gateway(amount: int, delay: float = 0.0):
    seq = count(1)
    calls: list[dict] = []

    async def create_order(*args, **kwargs):
        calls.append(kwargs)
        if delay:
            await asyncio.sleep(delay)
        return {
            "id": f"order_rzp_v2a_{uuid.uuid4().hex[:8]}_{next(seq)}",
            "amount": amount,
            "currency": "INR",
            "status": "created",
        }

    return create_order, calls


async def _attempts(order_id: str) -> int:
    async with get_session_factory()() as s:
        return (
            await s.execute(
                select(func.count())
                .select_from(Payment)
                .where(Payment.order_id == uuid.UUID(order_id))
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_repeat_without_key_reuses_pending_attempt(async_client: AsyncClient):
    _, _, order = await setup_customer_and_order(async_client)
    gw, calls = _fake_gateway(order["total_payable_paise"])
    url = f"/api/v1/orders/{order['id']}/payments"
    with patch.object(RazorpayClient, "create_order", side_effect=gw):
        r1 = await async_client.post(url)
        r2 = await async_client.post(url)
        r3 = await async_client.post(url)
    assert r1.status_code == r2.status_code == r3.status_code == 201, r2.text
    assert (
        r1.json()["provider_order_id"]
        == r2.json()["provider_order_id"]
        == r3.json()["provider_order_id"]
    )
    assert r1.json()["payment_id"] == r3.json()["payment_id"]
    assert len(calls) == 1
    assert await _attempts(order["id"]) == 1


@pytest.mark.asyncio
async def test_repeat_with_same_key_replays_and_keyless_then_reuses(
    async_client: AsyncClient,
):
    _, _, order = await setup_customer_and_order(async_client)
    gw, calls = _fake_gateway(order["total_payable_paise"])
    url = f"/api/v1/orders/{order['id']}/payments"
    with patch.object(RazorpayClient, "create_order", side_effect=gw):
        k1 = await async_client.post(url, headers={"Idempotency-Key": "v2a-key-1"})
        k2 = await async_client.post(url, headers={"Idempotency-Key": "v2a-key-1"})
        bare = await async_client.post(url)
    assert k1.status_code == k2.status_code == bare.status_code == 201
    assert (
        k1.json()["payment_id"] == k2.json()["payment_id"] == bare.json()["payment_id"]
    )
    assert len(calls) == 1 and await _attempts(order["id"]) == 1


@pytest.mark.asyncio
async def test_new_attempt_allowed_after_failed_attempt(async_client: AsyncClient):
    _, _, order = await setup_customer_and_order(async_client)
    gw, calls = _fake_gateway(order["total_payable_paise"])
    url = f"/api/v1/orders/{order['id']}/payments"
    with patch.object(RazorpayClient, "create_order", side_effect=gw):
        first = await async_client.post(url)
        assert first.status_code == 201
        async with get_session_factory()() as s:
            await s.execute(
                update(Payment)
                .where(Payment.id == uuid.UUID(first.json()["payment_id"]))
                .values(status=PaymentAttemptStatus.FAILED.value)
            )
            await s.commit()
        second = await async_client.post(url)
    assert second.status_code == 201, second.text
    assert second.json()["payment_id"] != first.json()["payment_id"]
    assert second.json()["provider_order_id"] != first.json()["provider_order_id"]
    assert second.json()["attempt_number"] == first.json()["attempt_number"] + 1
    assert len(calls) == 2 and await _attempts(order["id"]) == 2


@pytest.mark.asyncio
async def test_five_concurrent_keyless_initiations_create_one_attempt(
    async_client: AsyncClient,
):
    _, _, order = await setup_customer_and_order(async_client)
    gw, calls = _fake_gateway(order["total_payable_paise"], delay=0.1)
    url = f"/api/v1/orders/{order['id']}/payments"
    with patch.object(RazorpayClient, "create_order", side_effect=gw):
        responses = await asyncio.gather(*[async_client.post(url) for _ in range(5)])
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    assert len({r.json()["provider_order_id"] for r in responses}) == 1
    assert len(calls) == 1
    assert await _attempts(order["id"]) == 1


@pytest.mark.asyncio
async def test_different_explicit_keys_still_behave_as_before(
    async_client: AsyncClient,
):
    """Explicit distinct keys keep v1.0 semantics (a deliberate new attempt)."""
    _, _, order = await setup_customer_and_order(async_client)
    gw, calls = _fake_gateway(order["total_payable_paise"])
    url = f"/api/v1/orders/{order['id']}/payments"
    with patch.object(RazorpayClient, "create_order", side_effect=gw):
        a = await async_client.post(url, headers={"Idempotency-Key": "v2a-a"})
        b = await async_client.post(url, headers={"Idempotency-Key": "v2a-b"})
    assert a.status_code == b.status_code == 201
    assert a.json()["payment_id"] != b.json()["payment_id"]
    assert len(calls) == 2
