import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.config import settings
from app.core.database import get_session_factory
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OutboxEvent,
    PaymentStatus,
)
from app.modules.payments.client import RazorpayClient
from app.modules.payments.models import (
    CaptureReconciliationStatus,
    CaptureStatus,
    Payment,
    PaymentAttemptStatus,
    PaymentCapture,
    PaymentRefund,
    WebhookEvent,
)


def get_internal_auth_headers() -> dict[str, str]:
    assert settings.INTERNAL_SERVICE_KEY is not None
    key = settings.INTERNAL_SERVICE_KEY.get_secret_value()
    return {"X-Internal-Service-Key": key}


def generate_payment_signature(razorpay_order_id: str, razorpay_payment_id: str) -> str:
    secret = settings.RAZORPAY_KEY_SECRET.get_secret_value()
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def generate_webhook_signature(payload_bytes: bytes) -> str:
    secret = settings.RAZORPAY_WEBHOOK_SECRET.get_secret_value()
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


async def get_test_listing(async_client: AsyncClient, min_stock: int = 5) -> dict:
    response = await async_client.get("/api/v1/products?limit=10")
    assert response.status_code == 200
    for prod in response.json()["items"]:
        detail_resp = await async_client.get(f"/api/v1/products/{prod['id']}")
        assert detail_resp.status_code == 200
        for variant in detail_resp.json().get("variants", []):
            for listing in variant.get("listings", []):
                if (
                    listing.get("is_active")
                    and listing.get("available_quantity", 0) >= min_stock
                ):
                    return listing
    raise RuntimeError("No active test listing with sufficient stock found.")


async def setup_customer_and_order(
    client: AsyncClient,
) -> tuple[dict, str, dict]:
    """Helper to register customer, address, cart, quote, reservation, and order."""
    listing = await get_test_listing(client)
    listing_id = listing["id"]

    email = f"pay_cust_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": "Payment Test User",
            "phone": "+919876543210",
        },
    )
    assert reg_resp.status_code == 201
    token = reg_resp.json()["access_token"]
    user_data = reg_resp.json()["user"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    addr_resp = await client.post(
        "/api/v1/addresses",
        json={
            "recipient_name": "Payment Test User",
            "phone": "+919876543210",
            "line1": "100 Feet Road",
            "city": "Bengaluru",
            "state": "KA",
            "postal_code": "560038",
            "is_default": True,
        },
    )
    assert addr_resp.status_code == 201
    addr_id = addr_resp.json()["id"]

    await client.post(
        "/api/v1/cart/items",
        json={"listing_id": listing_id, "quantity": 1},
    )
    q_resp = await client.post("/api/v1/quotes", json={"delivery_address_id": addr_id})
    assert q_resp.status_code == 201
    quote_id = q_resp.json()["id"]

    r_resp = await client.post("/api/v1/reservations", json={"quote_id": quote_id})
    assert r_resp.status_code == 201
    res_id = r_resp.json()["id"]

    order_resp = await client.post(
        "/api/v1/orders",
        json={
            "quote_id": quote_id,
            "reservation_id": res_id,
            "delivery_address_id": addr_id,
        },
    )
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    return user_data, token, order_data


# ==============================================================================
# Group 1: Payment Initiation Scenarios
# ==============================================================================


@pytest.mark.asyncio
async def test_payment_initiation_happy_path_and_idempotency(
    async_client: AsyncClient,
):
    """Initiate payment persists CREATING attempt, calls Razorpay, returns PENDING attempt, and is idempotent."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]

    fake_provider_order = {
        "id": "order_rzp_mock_123",
        "amount": order["total_payable_paise"],
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }

    with patch.object(
        RazorpayClient, "create_order", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = fake_provider_order

        # First initiation
        resp1 = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={"Idempotency-Key": "idemp-init-1"},
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["provider_order_id"] == "order_rzp_mock_123"
        assert data1["amount_paise"] == order["total_payable_paise"]
        assert data1["status"] == "PENDING"
        assert mock_create.call_count == 1

        # Second initiation with same idempotency key: should return existing attempt without re-calling Razorpay
        resp2 = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={"Idempotency-Key": "idemp-init-1"},
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["payment_id"] == data1["payment_id"]
        assert data2["provider_order_id"] == "order_rzp_mock_123"
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_concurrent_payment_initiation_deduplication(
    async_client: AsyncClient,
):
    """5 concurrent identical requests for the same order create exactly 1 provider order."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]

    fake_provider_order = {
        "id": "order_rzp_concurrent_999",
        "amount": order["total_payable_paise"],
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }

    async def slow_create_order(*args, **kwargs):
        await asyncio.sleep(0.05)
        return fake_provider_order

    with patch.object(
        RazorpayClient, "create_order", side_effect=slow_create_order
    ) as mock_create:
        # Launch 5 concurrent requests
        tasks = [
            async_client.post(
                f"/api/v1/orders/{order_id}/payments",
                headers={"Idempotency-Key": "idemp-concurrent-key"},
            )
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        for r in responses:
            assert r.status_code == 201
            assert r.json()["provider_order_id"] == "order_rzp_concurrent_999"

        # Exactly 1 provider order created
        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_payment_initiation_cancelled_order_rejected(
    async_client: AsyncClient,
):
    """Cancelled order cannot initiate payment."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])

    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=OrderStatus.CANCELLED)
        )
        await session.commit()

    resp = await async_client.post(f"/api/v1/orders/{order_id}/payments")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ORDER_NOT_PAYABLE"


@pytest.mark.asyncio
async def test_payment_ownership_isolation(
    async_client: AsyncClient,
):
    """Another customer cannot initiate payment on someone else's order."""
    user1, token1, order = await setup_customer_and_order(async_client)
    order_id = order["id"]

    # Register customer 2
    email2 = f"other_cust_{uuid.uuid4().hex[:8]}@example.com"
    reg_resp2 = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email2,
            "password": "Password123!",
            "full_name": "Other User",
            "phone": "+919876543211",
        },
    )
    assert reg_resp2.status_code == 201
    token2 = reg_resp2.json()["access_token"]
    async_client.headers.update({"Authorization": f"Bearer {token2}"})

    resp = await async_client.post(f"/api/v1/orders/{order_id}/payments")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "ORDER_NOT_FOUND"


# ==============================================================================
# Group 2: Signature Verification & Multi-factor Capture Scenarios
# ==============================================================================


@pytest.mark.asyncio
async def test_payment_verification_valid_signature_fulfills_order(
    async_client: AsyncClient,
):
    """Valid signature verification captures payment, confirms order, sets fulfilling_capture_id, and enqueues outbox event."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_provider_payment = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_provider_payment,
        ),
    ):
        # 1. Initiate payment
        init_resp = await async_client.post(f"/api/v1/orders/{order_id}/payments")
        assert init_resp.status_code == 201

        # 2. Verify payment
        verify_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )
        assert verify_resp.status_code == 200
        verify_data = verify_resp.json()
        assert verify_data["status"] == "CONFIRMED"
        assert verify_data["payment_status"] == "SUCCEEDED"

    # Verify DB state directly
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        assert db_order.status == OrderStatus.CONFIRMED
        assert db_order.payment_status == PaymentStatus.SUCCEEDED
        assert db_order.fulfilling_capture_id is not None

        # Verify fulfilling capture record
        capture = (
            await session.execute(
                select(PaymentCapture).where(
                    PaymentCapture.id == db_order.fulfilling_capture_id
                )
            )
        ).scalar_one()
        assert capture.order_id == uuid.UUID(order_id)
        assert capture.amount_paise == amount
        assert capture.status == CaptureStatus.CAPTURED
        assert capture.is_fulfillment_eligible is True

        # Verify outbox event written
        outbox = (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "order.confirmed",
                    OutboxEvent.aggregate_id == uuid.UUID(order_id),
                )
            )
        ).scalar_one_or_none()
        assert outbox is not None


@pytest.mark.asyncio
async def test_payment_verification_invalid_signature_rejected(
    async_client: AsyncClient,
):
    """Tampered signature rejected with 400 SIGNATURE_VERIFICATION_FAILED."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]

    fake_provider_order = {
        "id": "order_rzp_tamper_123",
        "amount": order["total_payable_paise"],
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }

    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value=fake_provider_order,
    ):
        await async_client.post(f"/api/v1/orders/{order_id}/payments")

        resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": "order_rzp_tamper_123",
                "razorpay_payment_id": "pay_rzp_tamper_456",
                "razorpay_signature": "invalid_forged_signature_hex",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "SIGNATURE_VERIFICATION_FAILED"


@pytest.mark.asyncio
async def test_payment_authorized_alone_does_not_fulfill(
    async_client: AsyncClient,
):
    """Authorized status alone does not mark order confirmed or populate fulfilling_capture_id."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_auth_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_auth_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    # Payment status is authorized, NOT captured
    fake_provider_payment = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "authorized",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_provider_payment,
        ),
        patch.object(
            RazorpayClient,
            "capture_payment",
            new_callable=AsyncMock,
            return_value=fake_provider_payment,
        ),
    ):
        await async_client.post(f"/api/v1/orders/{order_id}/payments")

        verify_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )
        assert verify_resp.status_code == 400
        assert verify_resp.json()["error"]["code"] == "PAYMENT_NOT_CAPTURED"

    # Verify order in DB was NOT confirmed
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        assert db_order.status == OrderStatus.PENDING_PAYMENT
        assert db_order.fulfilling_capture_id is None


@pytest.mark.asyncio
async def test_verify_callback_and_webhook_race_produces_single_fulfillment(
    async_client: AsyncClient,
):
    """Concurrent verify callback and payment.captured webhook result in exactly one fulfillment."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_race_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_race_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_provider_payment = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_provider_payment,
        ),
    ):
        await async_client.post(f"/api/v1/orders/{order_id}/payments")

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_mock_123",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": fake_provider_payment,
                }
            },
            "created_at": int(datetime.now(UTC).timestamp()),
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        webhook_sig = generate_webhook_signature(body_bytes)

        # Fire both concurrently
        verify_task = async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )
        webhook_task = async_client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": webhook_sig,
                "X-Razorpay-Event-Id": f"evt_race_{uuid.uuid4().hex[:8]}",
            },
        )

        resp_v, resp_w = await asyncio.gather(verify_task, webhook_task)
        assert resp_v.status_code == 200
        assert resp_w.status_code == 200

    # Verify single fulfillment in DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        assert db_order.status == OrderStatus.CONFIRMED
        assert db_order.fulfilling_capture_id is not None

        # Verify only 1 eligible capture
        captures = (
            (
                await session.execute(
                    select(PaymentCapture).where(
                        PaymentCapture.order_id == uuid.UUID(order_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(captures) == 1
        assert captures[0].is_fulfillment_eligible is True


@pytest.mark.asyncio
async def test_second_distinct_capture_recorded_as_anomaly_and_auto_refunded(
    async_client: AsyncClient,
):
    """A second distinct capture for an already fulfilled order is marked ANOMALOUS with is_fulfillment_eligible=FALSE and auto-refunded."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_dup_{uuid.uuid4().hex[:8]}"
    provider_payment_id1 = f"pay_rzp_prim_{uuid.uuid4().hex[:8]}"
    provider_payment_id2 = f"pay_rzp_anom_{uuid.uuid4().hex[:8]}"
    sig1 = generate_payment_signature(provider_order_id, provider_payment_id1)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_payment1 = {
        "id": provider_payment_id1,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }
    fake_payment2 = {
        "id": provider_payment_id2,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }
    fake_refund_resp = {
        "id": f"rfnd_rzp_auto_{uuid.uuid4().hex[:8]}",
        "entity": "refund",
        "amount": amount,
        "currency": "INR",
        "payment_id": provider_payment_id2,
        "status": "processed",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_payment1,
        ),
        patch.object(
            RazorpayClient,
            "create_refund",
            new_callable=AsyncMock,
            return_value=fake_refund_resp,
        ),
    ):
        # 1. Initiate and verify payment 1 -> Order fulfilled
        await async_client.post(f"/api/v1/orders/{order_id}/payments")
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id1,
                "razorpay_signature": sig1,
            },
        )

        # 2. Ingest duplicate capture webhook with provider_payment_id2
        webhook_payload = {
            "entity": "event",
            "account_id": "acc_mock_123",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": fake_payment2,
                }
            },
            "created_at": int(datetime.now(UTC).timestamp()),
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        webhook_sig = generate_webhook_signature(body_bytes)

        w_resp = await async_client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": webhook_sig,
                "X-Razorpay-Event-Id": f"evt_anom_{uuid.uuid4().hex[:8]}",
            },
        )
        assert w_resp.status_code == 200

    # 3. Check DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        # Original fulfillment intact
        assert db_order.status == OrderStatus.CONFIRMED

        captures = (
            (
                await session.execute(
                    select(PaymentCapture)
                    .where(PaymentCapture.order_id == uuid.UUID(order_id))
                    .order_by(PaymentCapture.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(captures) == 2

        # Capture 1: fulfilling
        assert captures[0].provider_payment_id == provider_payment_id1
        assert captures[0].is_fulfillment_eligible is True
        assert db_order.fulfilling_capture_id == captures[0].id

        # Capture 2: anomalous, not eligible
        assert captures[1].provider_payment_id == provider_payment_id2
        assert captures[1].is_fulfillment_eligible is False
        assert (
            captures[1].reconciliation_status
            == CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value
        )

        # Automated refund queued
        refunds = (
            (
                await session.execute(
                    select(PaymentRefund).where(
                        PaymentRefund.capture_id == captures[1].id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(refunds) == 1
        assert refunds[0].amount_paise == amount
        assert "DUPLICATE_CAPTURE" in refunds[0].reason


@pytest.mark.asyncio
async def test_partial_capture_rejected_and_auto_refunded(
    async_client: AsyncClient,
):
    """Underpayment/partial capture is flagged ANOMALOUS, does NOT fulfill order, and triggers auto-refund."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    order_amount = order["total_payable_paise"]
    partial_amount = order_amount - 1000  # 10 INR less

    provider_order_id = f"order_rzp_part_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_part_{uuid.uuid4().hex[:8]}"

    fake_provider_order = {
        "id": provider_order_id,
        "amount": order_amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_partial_payment = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": partial_amount,
        "currency": "INR",
        "status": "captured",
    }
    fake_refund_resp = {
        "id": f"rfnd_rzp_part_{uuid.uuid4().hex[:8]}",
        "entity": "refund",
        "amount": partial_amount,
        "currency": "INR",
        "payment_id": provider_payment_id,
        "status": "processed",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "create_refund",
            new_callable=AsyncMock,
            return_value=fake_refund_resp,
        ),
    ):
        await async_client.post(f"/api/v1/orders/{order_id}/payments")

        webhook_payload = {
            "entity": "event",
            "account_id": "acc_mock_123",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": fake_partial_payment,
                }
            },
            "created_at": int(datetime.now(UTC).timestamp()),
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        webhook_sig = generate_webhook_signature(body_bytes)

        w_resp = await async_client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": webhook_sig,
                "X-Razorpay-Event-Id": f"evt_part_{uuid.uuid4().hex[:8]}",
            },
        )
        assert w_resp.status_code == 200

    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        # Order NOT confirmed
        assert db_order.status == OrderStatus.PENDING_PAYMENT
        assert db_order.fulfilling_capture_id is None

        captures = (
            (
                await session.execute(
                    select(PaymentCapture).where(
                        PaymentCapture.order_id == uuid.UUID(order_id)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(captures) == 1
        assert (
            captures[0].reconciliation_status
            == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
        )
        assert captures[0].is_fulfillment_eligible is False


@pytest.mark.asyncio
async def test_late_capture_after_cancellation_auto_refunded_no_stock_deduction(
    async_client: AsyncClient,
):
    """Late capture arriving after order cancellation/reservation release never fulfills order; auto-refunds without re-deducting stock."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])
    res_id = uuid.UUID(order["reservation_id"])
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_late_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_late_{uuid.uuid4().hex[:8]}"

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value=fake_provider_order,
    ):
        init_res = await async_client.post(f"/api/v1/orders/{order_id}/payments")
        assert init_res.status_code == 201

    # Cancel order and release reservation
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status=OrderStatus.CANCELLED)
        )
        await session.execute(
            update(InventoryReservation)
            .where(InventoryReservation.id == res_id)
            .values(status=ReservationStatus.RELEASED)
        )
        await session.commit()
    fake_payment = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }
    fake_refund_resp = {
        "id": f"rfnd_rzp_late_{uuid.uuid4().hex[:8]}",
        "entity": "refund",
        "amount": amount,
        "currency": "INR",
        "payment_id": provider_payment_id,
        "status": "processed",
    }

    with patch.object(
        RazorpayClient,
        "create_refund",
        new_callable=AsyncMock,
        return_value=fake_refund_resp,
    ):
        webhook_payload = {
            "entity": "event",
            "account_id": "acc_mock_123",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": fake_payment,
                }
            },
            "created_at": int(datetime.now(UTC).timestamp()),
        }
        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        webhook_sig = generate_webhook_signature(body_bytes)

        w_resp = await async_client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": webhook_sig,
                "X-Razorpay-Event-Id": f"evt_late_{uuid.uuid4().hex[:8]}",
            },
        )
        assert w_resp.status_code == 200

    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        # Remains CANCELLED
        assert db_order.status == OrderStatus.CANCELLED
        assert db_order.fulfilling_capture_id is None

        # Reservation remains RELEASED
        db_res = (
            await session.execute(
                select(InventoryReservation).where(InventoryReservation.id == res_id)
            )
        ).scalar_one()
        assert db_res.status == ReservationStatus.RELEASED

        # Capture is anomalous with auto-refund
        capture = (
            await session.execute(
                select(PaymentCapture).where(PaymentCapture.order_id == order_id)
            )
        ).scalar_one()
        assert (
            capture.reconciliation_status
            == CaptureReconciliationStatus.LATE_CAPTURE_ANOMALY.value
        )
        assert capture.is_fulfillment_eligible is False


# ==============================================================================
# Group 3: Live PostgreSQL Database Invariants
# ==============================================================================


@pytest.mark.asyncio
async def test_database_trigger_protects_immutable_capture_facts(
    async_client: AsyncClient,
):
    """PostgreSQL trigger trg_payment_captures_protect_immutable blocks UPDATE of immutable fields and DELETE."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])
    amount = order["total_payable_paise"]

    session_factory = get_session_factory()
    capture_id = uuid.uuid4()

    # Insert a valid capture row directly
    async with session_factory() as session:
        payment = Payment(
            id=uuid.uuid4(),
            order_id=order_id,
            customer_id=uuid.UUID(user["id"]),
            provider="RAZORPAY_SANDBOX",
            idempotency_key=f"idemp-trig-{uuid.uuid4().hex[:8]}",
            attempt_number=1,
            amount_paise=amount,
            currency="INR",
            status=PaymentAttemptStatus.PENDING.value,
        )
        session.add(payment)
        await session.flush()

        capture = PaymentCapture(
            id=capture_id,
            order_id=order_id,
            payment_id=payment.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=f"pay_rzp_trig_{uuid.uuid4().hex[:8]}",
            amount_paise=amount,
            currency="INR",
            status=CaptureStatus.CAPTURED.value,
            is_fulfillment_eligible=True,
            captured_at=datetime.now(UTC),
        )
        session.add(capture)
        await session.commit()

    # 1. Attempt UPDATE on immutable amount_paise -> trigger must raise exception
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                update(PaymentCapture)
                .where(PaymentCapture.id == capture_id)
                .values(amount_paise=999999)
            )
            await session.commit()
        assert (
            "immutable" in str(exc_info.value).lower()
            or "trg_payment_captures" in str(exc_info.value).lower()
        )

    # 2. Attempt UPDATE on is_fulfillment_eligible -> trigger must raise exception
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                update(PaymentCapture)
                .where(PaymentCapture.id == capture_id)
                .values(is_fulfillment_eligible=False)
            )
            await session.commit()
        assert (
            "immutable" in str(exc_info.value).lower()
            or "eligibility" in str(exc_info.value).lower()
        )

    # 3. Attempt DELETE on payment_captures -> trigger must raise exception
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                text("DELETE FROM payment_captures WHERE id = :id"),
                {"id": capture_id},
            )
            await session.commit()
        assert (
            "append-only" in str(exc_info.value).lower()
            or "cannot be deleted" in str(exc_info.value).lower()
        )


@pytest.mark.asyncio
async def test_database_trigger_and_fk_protect_order_fulfillment(
    async_client: AsyncClient,
):
    """Database triggers and composite foreign keys protect orders.fulfilling_capture_id."""
    user, token, order1 = await setup_customer_and_order(async_client)
    order1_id = uuid.UUID(order1["id"])

    # Create Order 2 for cross-order test
    user2, token2, order2 = await setup_customer_and_order(async_client)
    order2_id = uuid.UUID(order2["id"])

    session_factory = get_session_factory()
    cap1_id = uuid.uuid4()
    cap_ineligible_id = uuid.uuid4()

    async with session_factory() as session:
        pay1 = Payment(
            id=uuid.uuid4(),
            order_id=order1_id,
            customer_id=uuid.UUID(user["id"]),
            provider="RAZORPAY_SANDBOX",
            idempotency_key=f"idemp-fk-{uuid.uuid4().hex[:8]}",
            attempt_number=1,
            amount_paise=order1["total_payable_paise"],
            currency="INR",
            status=PaymentAttemptStatus.PENDING.value,
        )
        session.add(pay1)
        await session.flush()

        # Eligible capture for order1
        cap1 = PaymentCapture(
            id=cap1_id,
            order_id=order1_id,
            payment_id=pay1.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=f"pay_rzp_fk1_{uuid.uuid4().hex[:8]}",
            amount_paise=order1["total_payable_paise"],
            currency="INR",
            status=CaptureStatus.CAPTURED.value,
            is_fulfillment_eligible=True,
            captured_at=datetime.now(UTC),
        )
        # Ineligible capture for order1
        cap_ineligible = PaymentCapture(
            id=cap_ineligible_id,
            order_id=order1_id,
            payment_id=pay1.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=f"pay_rzp_inelig_{uuid.uuid4().hex[:8]}",
            amount_paise=order1["total_payable_paise"],
            currency="INR",
            status=CaptureStatus.CAPTURED.value,
            reconciliation_status=CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value,
            is_fulfillment_eligible=False,
            captured_at=datetime.now(UTC),
        )
        session.add_all([cap1, cap_ineligible])
        await session.commit()

    # 1. Attempt assigning ineligible capture to order1 -> trg_orders_fulfilling_capture_immutable raises
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                update(Order)
                .where(Order.id == order1_id)
                .values(fulfilling_capture_id=cap_ineligible_id)
            )
            await session.commit()
        assert (
            "not eligible" in str(exc_info.value).lower()
            or "ineligible" in str(exc_info.value).lower()
        )

    # 2. Attempt assigning capture belonging to Order 1 as fulfilling capture for Order 2 -> composite FK raises IntegrityError
    async with session_factory() as session:
        with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
            await session.execute(
                update(Order)
                .where(Order.id == order2_id)
                .values(fulfilling_capture_id=cap1_id)
            )
            await session.commit()
        assert (
            "fk_orders_fulfilling_capture_same_order" in str(exc_info.value).lower()
            or "foreign key" in str(exc_info.value).lower()
            or "illegal fulfillment" in str(exc_info.value).lower()
        )

    # 3. Assign eligible cap1 to order1 -> succeeds
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order1_id)
            .values(fulfilling_capture_id=cap1_id)
        )
        await session.commit()

    # 4. Attempt to clear fulfilling_capture_id (set to NULL) -> trigger blocks clearing
    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                update(Order)
                .where(Order.id == order1_id)
                .values(fulfilling_capture_id=None)
            )
            await session.commit()
        assert (
            "immutable" in str(exc_info.value).lower()
            or "cannot be cleared" in str(exc_info.value).lower()
        )

    # 5. Attempt to replace fulfilling_capture_id with another capture -> trigger blocks replacement
    another_cap_id = uuid.uuid4()
    async with session_factory() as session:
        another_cap = PaymentCapture(
            id=another_cap_id,
            order_id=order1_id,
            payment_id=pay1.id,
            provider="RAZORPAY_SANDBOX",
            provider_payment_id=f"pay_rzp_another_{uuid.uuid4().hex[:8]}",
            amount_paise=order1["total_payable_paise"],
            currency="INR",
            status=CaptureStatus.CAPTURED.value,
            is_fulfillment_eligible=True,
            captured_at=datetime.now(UTC),
        )
        session.add(another_cap)
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(DBAPIError) as exc_info:
            await session.execute(
                update(Order)
                .where(Order.id == order1_id)
                .values(fulfilling_capture_id=another_cap_id)
            )
            await session.commit()
        assert (
            "immutable" in str(exc_info.value).lower()
            or "cannot be replaced" in str(exc_info.value).lower()
        )


# ==============================================================================
# Group 4: Webhook Ingestion & Deduplication Scenarios
# ==============================================================================


@pytest.mark.asyncio
async def test_webhook_ingestion_valid_hmac_and_idempotent_duplicate(
    async_client: AsyncClient,
):
    """Valid webhook ingested and returns HTTP 200; duplicate event ID returns HTTP 200 immediately without re-processing."""
    event_id = f"evt_dedup_{uuid.uuid4().hex[:8]}"
    payload = {
        "entity": "event",
        "account_id": "acc_mock_123",
        "event": "payment.failed",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_rzp_fail_{uuid.uuid4().hex[:8]}",
                    "order_id": f"order_rzp_{uuid.uuid4().hex[:8]}",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "failed",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Payment failed by customer",
                }
            }
        },
        "created_at": int(datetime.now(UTC).timestamp()),
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = generate_webhook_signature(body_bytes)

    # Ingestion 1
    resp1 = await async_client.post(
        "/api/v1/payments/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "ok"

    # Ingestion 2 (identical duplicate event)
    resp2 = await async_client.post(
        "/api/v1/payments/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ignored"

    # Verify only 1 record in webhook_events
    session_factory = get_session_factory()
    async with session_factory() as session:
        events = (
            (
                await session.execute(
                    select(WebhookEvent).where(
                        WebhookEvent.provider_event_id == event_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1


@pytest.mark.asyncio
async def test_webhook_ingestion_invalid_hmac_rejected(
    async_client: AsyncClient,
):
    """Invalid webhook HMAC signature rejected with 400 WEBHOOK_SIGNATURE_INVALID."""
    body_bytes = b'{"entity":"event","event":"payment.captured"}'
    resp = await async_client.post(
        "/api/v1/payments/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_forged_hmac_hex",
            "X-Razorpay-Event-Id": f"evt_forged_{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_stale_payment_failed_cannot_regress_confirmed_order(
    async_client: AsyncClient,
):
    """Late or out-of-order payment.failed webhook cannot regress an already CONFIRMED order."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_stale_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_stale_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_payment_captured = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_payment_captured,
        ),
    ):
        # Initiate and verify to confirm order
        await async_client.post(f"/api/v1/orders/{order_id}/payments")
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )

        # Ingest stale payment.failed webhook
        failed_payload = {
            "entity": "event",
            "account_id": "acc_mock_123",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": provider_payment_id,
                        "order_id": provider_order_id,
                        "amount": amount,
                        "currency": "INR",
                        "status": "failed",
                        "error_code": "CUSTOMER_CANCELLED",
                    }
                }
            },
            "created_at": int(datetime.now(UTC).timestamp()),
        }
        body_bytes = json.dumps(failed_payload).encode("utf-8")
        w_sig = generate_webhook_signature(body_bytes)

        w_resp = await async_client.post(
            "/api/v1/payments/webhook",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": w_sig,
                "X-Razorpay-Event-Id": f"evt_fail_stale_{uuid.uuid4().hex[:8]}",
            },
        )
        assert w_resp.status_code == 200

    # Order must remain CONFIRMED and PAID
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == uuid.UUID(order_id)))
        ).scalar_one()
        assert db_order.status == OrderStatus.CONFIRMED
        assert db_order.payment_status == PaymentStatus.SUCCEEDED


# ==============================================================================
# Group 5: Refunds & Balance Invariants
# ==============================================================================


@pytest.mark.asyncio
async def test_partial_and_full_refund_flow(
    async_client: AsyncClient,
):
    """Customer requests partial refund, then full refund; balances and status updated properly."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_ref_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_ref_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_payment_captured = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }

    half_amount = amount // 2
    rem_amount = amount - half_amount

    fake_refund_1 = {
        "id": f"rfnd_rzp_part1_{uuid.uuid4().hex[:8]}",
        "entity": "refund",
        "amount": half_amount,
        "currency": "INR",
        "payment_id": provider_payment_id,
        "status": "processed",
    }
    fake_refund_2 = {
        "id": f"rfnd_rzp_part2_{uuid.uuid4().hex[:8]}",
        "entity": "refund",
        "amount": rem_amount,
        "currency": "INR",
        "payment_id": provider_payment_id,
        "status": "processed",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_payment_captured,
        ),
        patch.object(
            RazorpayClient, "create_refund", new_callable=AsyncMock
        ) as mock_refund,
    ):
        # 1. Pay order
        await async_client.post(f"/api/v1/orders/{order_id}/payments")
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )

        # 2. Request first partial refund
        mock_refund.return_value = fake_refund_1
        ref1_key = f"idemp-ref1-{uuid.uuid4().hex[:8]}"
        r_resp1 = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            json={"amount_paise": half_amount, "reason": "Customer return item 1"},
            headers={"Idempotency-Key": ref1_key},
        )
        assert r_resp1.status_code == 201
        assert r_resp1.json()["amount_paise"] == half_amount

        # Check DB order status: PARTIALLY_REFUNDED
        session_factory = get_session_factory()
        async with session_factory() as session:
            db_order = (
                await session.execute(
                    select(Order).where(Order.id == uuid.UUID(order_id))
                )
            ).scalar_one()
            assert db_order.payment_status == PaymentStatus.PARTIALLY_REFUNDED

            db_cap = (
                await session.execute(
                    select(PaymentCapture).where(
                        PaymentCapture.order_id == uuid.UUID(order_id)
                    )
                )
            ).scalar_one()
            assert db_cap.status == CaptureStatus.PARTIALLY_REFUNDED.value

        # 3. Request remaining refund
        mock_refund.return_value = fake_refund_2
        ref2_key = f"idemp-ref2-{uuid.uuid4().hex[:8]}"
        r_resp2 = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            json={"amount_paise": rem_amount, "reason": "Customer return item 2"},
            headers={"Idempotency-Key": ref2_key},
        )
        assert r_resp2.status_code == 201
        assert r_resp2.json()["amount_paise"] == rem_amount

        # Check DB order status: fully REFUNDED
        async with session_factory() as session:
            db_order = (
                await session.execute(
                    select(Order).where(Order.id == uuid.UUID(order_id))
                )
            ).scalar_one()
            assert db_order.payment_status == PaymentStatus.REFUNDED

            db_cap = (
                await session.execute(
                    select(PaymentCapture).where(
                        PaymentCapture.order_id == uuid.UUID(order_id)
                    )
                )
            ).scalar_one()
            assert db_cap.status == CaptureStatus.REFUNDED.value


@pytest.mark.asyncio
async def test_refund_exceeding_captured_amount_rejected(
    async_client: AsyncClient,
):
    """Attempting to refund more than the captured amount is rejected with 409 REFUND_EXCEEDS_CAPTURED_AMOUNT."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_ovr_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_ovr_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    fake_provider_order = {
        "id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "receipt": order["order_number"],
        "status": "created",
    }
    fake_payment_captured = {
        "id": provider_payment_id,
        "order_id": provider_order_id,
        "amount": amount,
        "currency": "INR",
        "status": "captured",
    }

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value=fake_provider_order,
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value=fake_payment_captured,
        ),
    ):
        await async_client.post(f"/api/v1/orders/{order_id}/payments")
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )

        resp = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            json={"amount_paise": amount + 5000},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "REFUND_EXCEEDS_CAPTURED_AMOUNT"


# ==============================================================================
# Group 6: 75-Minute SLA Escalation & Ambiguity Reconciliation
# ==============================================================================


@pytest.mark.asyncio
async def test_75m_sla_escalation_job_cancels_unpaid_order_and_releases_reservation(
    async_client: AsyncClient,
):
    """The 75-minute SLA job cancels expired unpaid orders, releases inventory reservations, marks pending payments FAILED, and is idempotent."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])
    res_id = uuid.UUID(order["reservation_id"])

    # Simulate expired payment window (80 minutes ago)
    past_expiry = datetime.now(UTC) - timedelta(minutes=80)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(
                created_at=past_expiry - timedelta(days=30),
                payment_window_expires_at=past_expiry,
            )
        )
        # Create a pending payment attempt
        pending_payment = Payment(
            id=uuid.uuid4(),
            order_id=order_id,
            customer_id=uuid.UUID(user["id"]),
            provider="RAZORPAY_SANDBOX",
            provider_order_id=f"order_rzp_sla_{uuid.uuid4().hex[:8]}",
            amount_paise=order["total_payable_paise"],
            currency="INR",
            status=PaymentAttemptStatus.PENDING.value,
            attempt_number=1,
            idempotency_key=f"idemp-sla-{uuid.uuid4().hex[:8]}",
            created_at=past_expiry,
        )
        session.add(pending_payment)
        await session.commit()

    # Run internal SLA job
    headers = get_internal_auth_headers()
    job_resp = await async_client.post(
        "/api/v1/internal/payments/sla-escalation",
        headers=headers,
    )
    assert job_resp.status_code == 200
    res_data = job_resp.json()
    assert res_data["cancelled_orders_count"] >= 1

    # Verify DB state
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert db_order.status == OrderStatus.CANCELLED

        db_res = (
            await session.execute(
                select(InventoryReservation).where(InventoryReservation.id == res_id)
            )
        ).scalar_one()
        assert db_res.status == ReservationStatus.RELEASED

        db_pay = (
            await session.execute(select(Payment).where(Payment.order_id == order_id))
        ).scalar_one()
        assert db_pay.status == PaymentAttemptStatus.FAILED.value

        # Verify outbox event written for order cancellation
        outbox = (
            await session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "order.cancelled",
                    OutboxEvent.aggregate_id == order_id,
                )
            )
        ).scalar_one_or_none()
        assert outbox is not None

    # Run SLA job second time -> idempotent
    job_resp2 = await async_client.post(
        "/api/v1/internal/payments/sla-escalation",
        headers=headers,
    )
    assert job_resp2.status_code == 200


@pytest.mark.asyncio
async def test_reconciliation_resolves_ambiguous_attempt(
    async_client: AsyncClient,
):
    """Reconciliation service inspects ambiguous attempt, queries Razorpay, and updates status."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])
    pay_id = uuid.uuid4()
    provider_order_id = f"order_rzp_recon_{uuid.uuid4().hex[:8]}"

    session_factory = get_session_factory()
    async with session_factory() as session:
        payment = Payment(
            id=pay_id,
            order_id=order_id,
            customer_id=uuid.UUID(user["id"]),
            provider="RAZORPAY_SANDBOX",
            provider_order_id=None,
            amount_paise=order["total_payable_paise"],
            currency="INR",
            status=PaymentAttemptStatus.CREATION_AMBIGUOUS.value,
            attempt_number=1,
            idempotency_key=f"idemp-recon-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(UTC) - timedelta(minutes=15),
        )
        session.add(payment)
        await session.commit()

    receipt_str = f"{order['order_number']}-1"[:40]
    fake_orders_resp = [
        {
            "id": provider_order_id,
            "amount": order["total_payable_paise"],
            "currency": "INR",
            "receipt": receipt_str,
            "status": "created",
        }
    ]

    with patch.object(
        RazorpayClient,
        "fetch_orders_by_receipt",
        new_callable=AsyncMock,
        return_value=fake_orders_resp,
    ):
        headers = get_internal_auth_headers()
        recon_resp = await async_client.post(
            "/api/v1/internal/payments/reconcile-pending",
            headers=headers,
        )
        assert recon_resp.status_code == 200

    async with session_factory() as session:
        db_pay = (
            await session.execute(select(Payment).where(Payment.id == pay_id))
        ).scalar_one()
        assert db_pay.status == PaymentAttemptStatus.PENDING.value
        assert db_pay.provider_order_id == provider_order_id
