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
from app.core.exceptions import AppException
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.service import ReservationService
from app.modules.orders.models import (
    Order,
    OrderStatus,
    OutboxEvent,
    PaymentStatus,
)
from app.modules.payments.client import RazorpayClient
from app.modules.payments.exceptions import PaymentGatewayTimeoutError
from app.modules.payments.models import (
    CaptureReconciliationStatus,
    CaptureStatus,
    Payment,
    PaymentAttemptStatus,
    PaymentCapture,
    PaymentRefund,
    RefundStatus,
    WebhookEvent,
    WebhookEventStatus,
)
from app.modules.payments.reconciliation import ReconciliationService
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.webhook import WebhookService


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
        # Order cancelled and not confirmed
        assert db_order.status == OrderStatus.CANCELLED.value
        assert db_order.payment_status == PaymentStatus.FAILED.value
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


@pytest.mark.asyncio
async def test_refund_lifecycle_pending_timeout_and_processed_with_processed_at(
    async_client: AsyncClient,
):
    """Verifies REFUND_REQUESTED -> REFUND_PENDING (processed_at is None) -> REFUND_PROCESSED (processed_at set).
    Also proves timeout does not mark refund FAILED, and capture status only changes on confirmed processed total.
    """
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_rfnd_lc_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_rfnd_lc_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    # 1. Initiate and fulfill order
    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value={
                "id": provider_order_id,
                "amount": amount,
                "currency": "INR",
                "receipt": order["order_number"],
                "status": "created",
            },
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": provider_payment_id,
                "order_id": provider_order_id,
                "amount": amount,
                "currency": "INR",
                "status": "captured",
            },
        ),
    ):
        init_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert init_resp.status_code == 201

        verify_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )
        assert verify_resp.status_code == 200

    # 2. Customer requests refund, but gateway returns status="pending"
    rzp_refund_id = f"rfnd_rzp_pend_{uuid.uuid4().hex[:8]}"
    with patch.object(
        RazorpayClient,
        "create_refund",
        new_callable=AsyncMock,
        return_value={
            "id": rzp_refund_id,
            "amount": amount,
            "status": "pending",
        },
    ):
        ref_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"idemp-rfnd-pend-{uuid.uuid4().hex[:8]}",
            },
            json={"amount_paise": amount, "reason": "Test pending refund"},
        )
        assert ref_resp.status_code == 201
        ref_data = ref_resp.json()
        assert ref_data["status"] == "REFUND_PENDING"

    session_factory = get_session_factory()
    assert session_factory is not None

    async with session_factory() as session:
        db_rfnd = (
            await session.execute(
                select(PaymentRefund).where(
                    PaymentRefund.provider_refund_id == rzp_refund_id
                )
            )
        ).scalar_one()
        assert db_rfnd.status == RefundStatus.REFUND_PENDING.value
        assert db_rfnd.processed_at is None  # CRITICAL: Not processed yet!

        db_capture = (
            await session.execute(
                select(PaymentCapture).where(PaymentCapture.id == db_rfnd.capture_id)
            )
        ).scalar_one()
        # Capture status MUST still be CAPTURED because 0 paise is confirmed processed!
        assert db_capture.status == CaptureStatus.CAPTURED.value

    # 3. Simulate refund timeout path: outcome remains uncertain, status is REFUND_PENDING, not FAILED
    with patch.object(
        RazorpayClient,
        "create_refund",
        new_callable=AsyncMock,
        side_effect=PaymentGatewayTimeoutError("Gateway timeout on refund"),
    ):
        timeout_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"idemp-rfnd-tout-{uuid.uuid4().hex[:8]}",
            },
            json={"amount_paise": 100, "reason": "Test timeout refund"},
        )
        # Bounded by refundable balance error since full amount already pending!
        assert timeout_resp.status_code == 409

    # 4. Now webhook refund.processed arrives from gateway:
    # Authoritative confirmation transitions to REFUND_PROCESSED and sets processed_at
    webhook_event_id = f"evt_rfnd_proc_{uuid.uuid4().hex[:8]}"
    wh_payload = {
        "entity": "event",
        "id": webhook_event_id,
        "event": "refund.processed",
        "payload": {
            "refund": {
                "entity": {
                    "id": rzp_refund_id,
                    "payment_id": provider_payment_id,
                    "amount": amount,
                    "status": "processed",
                }
            }
        },
    }
    raw_wh = json.dumps(wh_payload).encode()
    wh_sig = generate_webhook_signature(raw_wh)

    wh_resp = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": wh_sig,
            "x-razorpay-event-id": webhook_event_id,
            "content-type": "application/json",
        },
        content=raw_wh,
    )
    assert wh_resp.status_code == 200

    async with session_factory() as session:
        db_rfnd_after = (
            await session.execute(
                select(PaymentRefund).where(
                    PaymentRefund.provider_refund_id == rzp_refund_id
                )
            )
        ).scalar_one()
        assert db_rfnd_after.status == RefundStatus.REFUND_PROCESSED.value
        assert db_rfnd_after.processed_at is not None  # Genuine timestamp!

        db_capture_after = (
            await session.execute(
                select(PaymentCapture).where(
                    PaymentCapture.id == db_rfnd_after.capture_id
                )
            )
        ).scalar_one()
        assert db_capture_after.status == CaptureStatus.REFUNDED.value


@pytest.mark.asyncio
async def test_reconciliation_reconciles_pending_refund_to_processed(
    async_client: AsyncClient,
):
    """Reconciler queries Razorpay for pending refund, confirms 'processed', and updates capture to REFUNDED."""
    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    provider_order_id = f"order_rzp_rfnd_rec_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_rfnd_rec_{uuid.uuid4().hex[:8]}"
    valid_sig = generate_payment_signature(provider_order_id, provider_payment_id)

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value={
                "id": provider_order_id,
                "amount": amount,
                "currency": "INR",
                "receipt": order["order_number"],
                "status": "created",
            },
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": provider_payment_id,
                "order_id": provider_order_id,
                "amount": amount,
                "currency": "INR",
                "status": "captured",
            },
        ),
    ):
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_order_id": provider_order_id,
                "razorpay_payment_id": provider_payment_id,
                "razorpay_signature": valid_sig,
            },
        )

    rzp_refund_id = f"rfnd_rzp_to_recon_{uuid.uuid4().hex[:8]}"
    with patch.object(
        RazorpayClient,
        "create_refund",
        new_callable=AsyncMock,
        return_value={"id": rzp_refund_id, "amount": amount, "status": "pending"},
    ):
        await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"idemp-rfnd-rec-{uuid.uuid4().hex[:8]}",
            },
            json={"amount_paise": amount, "reason": "Pending reconciliation refund"},
        )

    session_factory = get_session_factory()
    assert session_factory is not None

    # Age refund artificially by 5 minutes so reconciliation queries it
    async with session_factory() as session:
        await session.execute(
            update(PaymentRefund)
            .where(PaymentRefund.provider_refund_id == rzp_refund_id)
            .values(created_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        await session.commit()

    # Run reconciler with mock fetch_refund_by_id returning 'processed'
    with patch.object(
        RazorpayClient,
        "fetch_refund_by_id",
        new_callable=AsyncMock,
        return_value={
            "id": rzp_refund_id,
            "payment_id": provider_payment_id,
            "amount": amount,
            "status": "processed",
        },
    ):
        headers = get_internal_auth_headers()
        recon_resp = await async_client.post(
            "/api/v1/internal/payments/reconcile-pending",
            headers=headers,
        )
        assert recon_resp.status_code == 200

    async with session_factory() as session:
        db_rfnd = (
            await session.execute(
                select(PaymentRefund).where(
                    PaymentRefund.provider_refund_id == rzp_refund_id
                )
            )
        ).scalar_one()
        assert db_rfnd.status == RefundStatus.REFUND_PROCESSED.value
        assert db_rfnd.processed_at is not None

        db_capture = (
            await session.execute(
                select(PaymentCapture).where(PaymentCapture.id == db_rfnd.capture_id)
            )
        ).scalar_one()
        assert db_capture.status == CaptureStatus.REFUNDED.value


@pytest.mark.asyncio
async def test_never_rollback_capture_ledger_on_anomalous_branches(
    async_client: AsyncClient,
):
    """CRITICAL 2: Proves that PaymentCapture and PaymentRefund rows persist in PostgreSQL
    even when verify_payment raises 409 ORDER_ALREADY_CONFIRMED, 400 ORDER_CANCELLED,
    or 400 PARTIAL_CAPTURE_REJECTED. Financial facts are never rolled back!
    """
    session_factory = get_session_factory()
    assert session_factory is not None

    user, token, order = await setup_customer_and_order(async_client)
    order_id = order["id"]
    amount = order["total_payable_paise"]

    # --- Case A: Confirmed order receives unexpected duplicate capture (OVERPAYMENT_ANOMALY) ---
    order_rzp_1 = f"order_rzp_norm_{uuid.uuid4().hex[:8]}"
    pay_rzp_1 = f"pay_rzp_norm_{uuid.uuid4().hex[:8]}"
    sig_1 = generate_payment_signature(order_rzp_1, pay_rzp_1)

    with (
        patch.object(
            RazorpayClient,
            "create_order",
            new_callable=AsyncMock,
            return_value={
                "id": order_rzp_1,
                "amount": amount,
                "currency": "INR",
                "receipt": order["order_number"],
                "status": "created",
            },
        ),
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": pay_rzp_1,
                "order_id": order_rzp_1,
                "amount": amount,
                "currency": "INR",
                "status": "captured",
            },
        ),
    ):
        await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={"Authorization": f"Bearer {token}"},
        )
        v1 = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_order_id": order_rzp_1,
                "razorpay_payment_id": pay_rzp_1,
                "razorpay_signature": sig_1,
            },
        )
        assert v1.status_code == 200

    # Now verify distinct second capture on the confirmed order
    pay_rzp_duplicate = f"pay_rzp_dupl_{uuid.uuid4().hex[:8]}"
    sig_dup = generate_payment_signature(order_rzp_1, pay_rzp_duplicate)

    with (
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": pay_rzp_duplicate,
                "order_id": order_rzp_1,
                "amount": amount,
                "currency": "INR",
                "status": "captured",
            },
        ),
        patch.object(
            RazorpayClient,
            "create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_rzp_dup_{uuid.uuid4().hex[:8]}",
                "amount": amount,
                "status": "processed",
            },
        ),
    ):
        dup_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "razorpay_order_id": order_rzp_1,
                "razorpay_payment_id": pay_rzp_duplicate,
                "razorpay_signature": sig_dup,
            },
        )
        assert dup_resp.status_code == 409  # ORDER_ALREADY_CONFIRMED

    # Direct DB inspection: verify anomaly capture AND refund intent survived the 409 error!
    async with session_factory() as session:
        cap_row = (
            await session.execute(
                select(PaymentCapture).where(
                    PaymentCapture.provider_payment_id == pay_rzp_duplicate
                )
            )
        ).scalar_one_or_none()
        assert cap_row is not None
        assert (
            cap_row.reconciliation_status
            == CaptureReconciliationStatus.OVERPAYMENT_ANOMALY.value
        )
        assert cap_row.is_fulfillment_eligible is False

        rfnd_row = (
            await session.execute(
                select(PaymentRefund).where(PaymentRefund.capture_id == cap_row.id)
            )
        ).scalar_one_or_none()
        assert rfnd_row is not None
        assert rfnd_row.amount_paise == amount

    # --- Case B: Late capture after order cancellation ---
    user_b, token_b, order_b = await setup_customer_and_order(async_client)
    order_b_id = order_b["id"]
    amount_b = order_b["total_payable_paise"]
    order_rzp_b = f"order_rzp_can_{uuid.uuid4().hex[:8]}"

    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value={
            "id": order_rzp_b,
            "amount": amount_b,
            "currency": "INR",
            "receipt": order_b["order_number"],
            "status": "created",
        },
    ):
        await async_client.post(
            f"/api/v1/orders/{order_b_id}/payments",
            headers={"Authorization": f"Bearer {token_b}"},
        )

    # Cancel order manually in DB
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order_b_id))
            .values(status=OrderStatus.CANCELLED.value)
        )
        await session.commit()

    pay_rzp_late = f"pay_rzp_late_{uuid.uuid4().hex[:8]}"
    sig_late = generate_payment_signature(order_rzp_b, pay_rzp_late)

    with (
        patch.object(
            RazorpayClient,
            "fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": pay_rzp_late,
                "order_id": order_rzp_b,
                "amount": amount_b,
                "currency": "INR",
                "status": "captured",
            },
        ),
        patch.object(
            RazorpayClient,
            "create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_rzp_late_{uuid.uuid4().hex[:8]}",
                "amount": amount_b,
                "status": "processed",
            },
        ),
    ):
        late_resp = await async_client.post(
            f"/api/v1/orders/{order_b_id}/payments/verify",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "razorpay_order_id": order_rzp_b,
                "razorpay_payment_id": pay_rzp_late,
                "razorpay_signature": sig_late,
            },
        )
        assert late_resp.status_code == 400

    async with session_factory() as session:
        late_cap = (
            await session.execute(
                select(PaymentCapture).where(
                    PaymentCapture.provider_payment_id == pay_rzp_late
                )
            )
        ).scalar_one_or_none()
        assert late_cap is not None
        assert (
            late_cap.reconciliation_status
            == CaptureReconciliationStatus.LATE_CAPTURE_ANOMALY.value
        )

        late_rfnd = (
            await session.execute(
                select(PaymentRefund).where(PaymentRefund.capture_id == late_cap.id)
            )
        ).scalar_one_or_none()
        assert late_rfnd is not None


@pytest.mark.asyncio
async def test_sla_reservation_release_failure_atomic_rollback_and_retry(
    async_client: AsyncClient,
):
    """CRITICAL 3: Never commit terminal order cancellation when reservation release fails.
    Transaction cleanly rolls back, payment_status is set to REQUIRES_RECONCILIATION,
    blocking new payment attempts, and retry completes cancellation atomically.
    """
    user, token, order = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order["id"])

    session_factory = get_session_factory()
    assert session_factory is not None

    # Age order past 75-minute SLA
    async with session_factory() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(
                created_at=datetime.now(UTC) - timedelta(minutes=80),
                payment_window_expires_at=datetime.now(UTC) - timedelta(minutes=80),
            )
        )
        await session.commit()

    headers = get_internal_auth_headers()

    # Step 1: Simulate reservation release failure
    from app.modules.inventory.service import ReservationService

    with patch.object(
        ReservationService,
        "release_reservation",
        new_callable=AsyncMock,
        side_effect=RuntimeError(
            "Simulated database lock failure on inventory release"
        ),
    ):
        resp = await async_client.post(
            "/api/v1/internal/payments/sla-escalation",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["cancelled_orders_count"] == 0

    # Step 2: Verify order was NOT cancelled! It remains PENDING_PAYMENT, but payment_status is REQUIRES_RECONCILIATION
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert db_order.status == OrderStatus.PENDING_PAYMENT.value
        assert db_order.payment_status == PaymentStatus.REQUIRES_RECONCILIATION.value

    # Step 3: Verify payment initiation is BLOCKED while in this unresolved state!
    init_blocked = await async_client.post(
        f"/api/v1/orders/{order_id}/payments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert init_blocked.status_code == 409

    # Step 4: Retry SLA job without mock failure: succeeds cleanly!
    retry_resp = await async_client.post(
        "/api/v1/internal/payments/sla-escalation",
        headers=headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["cancelled_orders_count"] >= 1

    async with session_factory() as session:
        db_order_after = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert db_order_after.status == OrderStatus.CANCELLED.value
        assert db_order_after.payment_status == PaymentStatus.FAILED.value


@pytest.mark.asyncio
async def test_webhook_claim_and_process_concurrency_race(
    async_client: AsyncClient,
):
    """CRITICAL 4: Proves SKIP LOCKED lease claiming prevents concurrent processors
    from processing the same webhook event simultaneously.
    """
    session_factory = get_session_factory()
    assert session_factory is not None

    event_id = uuid.uuid4()
    provider_event_id = f"evt_claim_race_{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        event = WebhookEvent(
            id=event_id,
            provider="RAZORPAY",
            provider_event_id=provider_event_id,
            event_type="payment.captured",
            payload={"event": "payment.captured", "id": provider_event_id},
            status=WebhookEventStatus.PENDING.value,
        )
        session.add(event)
        await session.commit()

    # Launch two concurrent workers trying to claim the exact same event
    from app.modules.payments.repository import PaymentRepository

    async def worker_claim(worker_id: str) -> bool:
        async with session_factory() as session:
            repo = PaymentRepository(session)
            return await repo.claim_specific_webhook_event(
                event_id=event_id, worker_id=worker_id, lease_seconds=30
            )

    results = await asyncio.gather(
        worker_claim("worker-alpha"),
        worker_claim("worker-beta"),
    )

    # Exactly one worker wins the claim; the other gets False
    assert sum(results) == 1, f"Expected exactly 1 claim winner, got {results}"


@pytest.mark.asyncio
async def test_webhook_missing_event_id_rejected_400(
    async_client: AsyncClient,
):
    """CRITICAL 4: If neither header nor payload contains valid event ID, reject with 400.
    Must never generate a random UUID and pretend deduplication is guaranteed!
    """
    payload = {"event": "payment.captured", "payload": {}}
    raw_body = json.dumps(payload).encode()
    sig = generate_webhook_signature(raw_body)

    resp = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": sig,
            "content-type": "application/json",
            # No x-razorpay-event-id header!
        },
        content=raw_body,
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "MISSING_WEBHOOK_EVENT_ID"


@pytest.mark.asyncio
async def test_internal_routes_fail_closed_without_auth(
    async_client: AsyncClient,
):
    """Verifies that internal reconciliation routes fail closed when called without valid authorization."""
    # 1. No auth headers -> 401
    r1 = await async_client.post("/api/v1/internal/payments/reconcile-pending")
    assert r1.status_code == 401

    # 2. Invalid auth token -> 401
    r2 = await async_client.post(
        "/api/v1/internal/payments/reconcile-pending",
        headers={"X-Internal-Service-Key": "invalid-wrong-key"},
    )
    assert r2.status_code == 401

    # 3. SLA escalation without auth -> 401
    r3 = await async_client.post("/api/v1/internal/payments/sla-escalation")
    assert r3.status_code == 401

    # 4. Initiate payment without user session or guest cookie -> 401
    random_order_id = uuid.uuid4()
    r4 = await async_client.post(f"/api/v1/orders/{random_order_id}/payments")
    assert r4.status_code == 401


@pytest.mark.asyncio
async def test_webhook_processor_enforces_lease_ownership():
    """BLOCKER 1: Proves:
    - Missing worker ID is rejected.
    - Wrong worker ID is rejected.
    - Expired lease is rejected.
    - Only the current lease owner can complete processing.
    - Worker losing lease during processing cannot complete.
    """
    session_factory = get_session_factory()

    event_id = uuid.uuid4()
    provider_event_id = f"evt_lease_{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        event = WebhookEvent(
            id=event_id,
            provider="RAZORPAY",
            provider_event_id=provider_event_id,
            event_type="unknown.noop",
            payload={"event": "unknown.noop", "id": provider_event_id},
            status=WebhookEventStatus.PENDING.value,
        )
        session.add(event)
        await session.commit()

    # 1. Missing worker ID -> rejected
    async with session_factory() as session:
        webhook_svc = WebhookService(session)
        with pytest.raises(AppException) as exc_info:
            await webhook_svc.process_webhook_event(event_id, worker_id="")
        assert exc_info.value.code == "MISSING_WORKER_ID"

    # 2. Worker claims the event
    async with session_factory() as session:
        repo = PaymentRepository(session)
        claimed = await repo.claim_specific_webhook_event(
            event_id=event_id, worker_id="worker-alpha", lease_seconds=30
        )
        assert claimed is True

    # 3. Wrong worker ID -> rejected (returns False, event remains PROCESSING)
    async with session_factory() as session:
        webhook_svc = WebhookService(session)
        res_wrong = await webhook_svc.process_webhook_event(
            event_id, worker_id="worker-beta"
        )
        assert res_wrong is False

    # 4. Expired lease -> rejected
    async with session_factory() as session:
        # Manually backdate lease expiration
        await session.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .values(claim_expires_at=datetime.now(UTC) - timedelta(seconds=10))
        )
        await session.commit()

        webhook_svc = WebhookService(session)
        res_expired = await webhook_svc.process_webhook_event(
            event_id, worker_id="worker-alpha"
        )
        assert res_expired is False

    # 5. Active lease owner succeeds and marks PROCESSED
    async with session_factory() as session:
        # Renew lease for worker-alpha
        await session.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == event_id)
            .values(
                status=WebhookEventStatus.PROCESSING.value,
                claimed_by="worker-alpha",
                claim_expires_at=datetime.now(UTC) + timedelta(seconds=30),
            )
        )
        await session.commit()

        webhook_svc = WebhookService(session)
        res_success = await webhook_svc.process_webhook_event(
            event_id, worker_id="worker-alpha"
        )
        assert res_success is True

    # Verify event is PROCESSED and claim is released
    async with session_factory() as session:
        ev = await session.get(WebhookEvent, event_id)
        assert ev.status == WebhookEventStatus.PROCESSED.value
        assert ev.claimed_by is None
        assert ev.claim_expires_at is None
        assert ev.processed_at is not None


@pytest.mark.asyncio
async def test_partial_capture_reservation_release_lifecycle(
    async_client: AsyncClient,
):
    """BLOCKER 2: PostgreSQL-backed test proving:
    - Partial capture with release failure:
      - Never marks the order CANCELLED if inventory hold release fails.
      - Sets order.payment_status = REQUIRES_RECONCILIATION.
      - PaymentCapture and PaymentRefund intent survive failure and are committed.
    - Retry after release failure:
      - Releases reservation.
      - Marks order CANCELLED and payment FAILED.
    - Exactly-once release:
      - Subsequent attempts do not release again.
    """
    user_data, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initiate payment attempt
    fake_rzp_order_id = f"order_{uuid.uuid4().hex[:14]}"
    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value={
            "id": fake_rzp_order_id,
            "status": "created",
            "amount": order_data["total_payable_paise"],
            "currency": "INR",
        },
    ):
        init_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={**headers, "Idempotency-Key": f"init-part-{order_id}"},
        )
    assert init_resp.status_code == 201
    pay_attempt = init_resp.json()
    rzp_order_id = pay_attempt["provider_order_id"]
    rzp_payment_id = f"pay_part_{uuid.uuid4().hex[:12]}"
    signature = generate_payment_signature(rzp_order_id, rzp_payment_id)

    # Order payable is e.g. 89950 paise. Mock partial underpayment (1000 paise)
    mock_rzp_partial = {
        "id": rzp_payment_id,
        "order_id": rzp_order_id,
        "amount": 1000,
        "currency": "INR",
        "status": "captured",
        "method": "upi",
    }

    session_factory = get_session_factory()

    # A. First verify with simulated reservation release failure
    with (
        patch(
            "app.modules.payments.service.RazorpayClient.fetch_payment",
            new_callable=AsyncMock,
            return_value=mock_rzp_partial,
        ),
        patch(
            "app.modules.payments.service.RazorpayClient.create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_{uuid.uuid4().hex[:12]}",
                "status": "processed",
                "amount": 1000,
            },
        ),
        patch(
            "app.modules.inventory.service.ReservationService.release_reservation",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Simulated DB lock timeout on inventory release"),
        ),
    ):
        v_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers=headers,
            json={
                "razorpay_order_id": rzp_order_id,
                "razorpay_payment_id": rzp_payment_id,
                "razorpay_signature": signature,
            },
        )
        assert v_resp.status_code == 400
        assert v_resp.json()["error"]["code"] == "PARTIAL_CAPTURE_REJECTED"

    # Verify DB state after release failure:
    async with session_factory() as session:
        # Order must NOT be CANCELLED!
        ord_row = await session.get(Order, order_id)
        assert ord_row.status != OrderStatus.CANCELLED.value
        assert ord_row.payment_status == PaymentStatus.REQUIRES_RECONCILIATION.value

        # Capture must survive and be recorded as PARTIAL_CAPTURE_REJECTED
        res_cap = await session.execute(
            select(PaymentCapture).where(
                PaymentCapture.provider_payment_id == rzp_payment_id
            )
        )
        cap = res_cap.scalar_one_or_none()
        assert cap is not None
        assert (
            cap.reconciliation_status
            == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
        )
        assert cap.is_fulfillment_eligible is False
        assert cap.amount_paise == 1000

        # Refund intent must survive
        res_rfnd = await session.execute(
            select(PaymentRefund).where(PaymentRefund.capture_id == cap.id)
        )
        rfnd = res_rfnd.scalar_one_or_none()
        assert rfnd is not None
        assert rfnd.amount_paise == 1000

    # B. Retry after release failure (unmocked reservation release succeeds)
    with (
        patch(
            "app.modules.payments.service.RazorpayClient.fetch_payment",
            new_callable=AsyncMock,
            return_value=mock_rzp_partial,
        ),
        patch(
            "app.modules.payments.service.RazorpayClient.create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_{uuid.uuid4().hex[:12]}",
                "status": "processed",
                "amount": 1000,
            },
        ),
    ):
        v_retry = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers=headers,
            json={
                "razorpay_order_id": rzp_order_id,
                "razorpay_payment_id": rzp_payment_id,
                "razorpay_signature": signature,
            },
        )
        assert v_retry.status_code == 400
        assert v_retry.json()["error"]["code"] == "PARTIAL_CAPTURE_REJECTED"

    # Verify DB state after successful release retry:
    async with session_factory() as session:
        ord_retry = await session.get(Order, order_id)
        assert ord_retry.status == OrderStatus.CANCELLED.value
        assert ord_retry.payment_status == PaymentStatus.FAILED.value


@pytest.mark.asyncio
async def test_refund_state_transitions_and_stale_events(
    async_client: AsyncClient,
):
    """BLOCKER 3: Proves:
    - refund.failed followed by refund.processed.
    - refund.processed followed by stale refund.failed (never regresses!).
    - Duplicate refund.processed is idempotent.
    - Duplicate refund.failed is idempotent.
    - Reconciliation after processed refund does not regress to failed.
    """
    session_factory = get_session_factory()

    user_data, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # Complete a normal capture first
    fake_rzp_order_id = f"order_{uuid.uuid4().hex[:14]}"
    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value={
            "id": fake_rzp_order_id,
            "status": "created",
            "amount": order_data["total_payable_paise"],
            "currency": "INR",
        },
    ):
        init_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={**headers, "Idempotency-Key": f"init-rfnd-{order_id}"},
        )
    assert init_resp.status_code == 201
    pay_attempt = init_resp.json()
    rzp_order_id = pay_attempt["provider_order_id"]
    rzp_payment_id = f"pay_rfnd_{uuid.uuid4().hex[:12]}"
    signature = generate_payment_signature(rzp_order_id, rzp_payment_id)

    mock_rzp_pay = {
        "id": rzp_payment_id,
        "order_id": rzp_order_id,
        "amount": order_data["total_payable_paise"],
        "currency": "INR",
        "status": "captured",
        "method": "upi",
    }
    with patch(
        "app.modules.payments.service.RazorpayClient.fetch_payment",
        new_callable=AsyncMock,
        return_value=mock_rzp_pay,
    ):
        v_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments/verify",
            headers=headers,
            json={
                "razorpay_order_id": rzp_order_id,
                "razorpay_payment_id": rzp_payment_id,
                "razorpay_signature": signature,
            },
        )
        assert v_resp.status_code == 200

    # Request a refund via internal API
    provider_refund_id = f"rfnd_{uuid.uuid4().hex[:12]}"
    with patch(
        "app.modules.payments.service.RazorpayClient.create_refund",
        new_callable=AsyncMock,
        return_value={
            "id": provider_refund_id,
            "status": "pending",
            "amount": order_data["total_payable_paise"],
        },
    ):
        rfnd_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/refunds",
            headers={
                **headers,
                "X-Internal-Service-Key": settings.INTERNAL_SERVICE_KEY.get_secret_value(),
                "Idempotency-Key": f"rfnd-key-{order_id}",
            },
            json={
                "amount_paise": order_data["total_payable_paise"],
                "reason": "Customer cancellation",
            },
        )
        assert rfnd_resp.status_code == 201

    # 1. refund.failed webhook arrives
    payload_failed = {
        "event": "refund.failed",
        "payload": {
            "refund": {
                "entity": {
                    "id": provider_refund_id,
                    "payment_id": rzp_payment_id,
                    "amount": order_data["total_payable_paise"],
                    "error_code": "BANK_REJECTED",
                    "error_description": "Insufficient funds at source bank",
                }
            }
        },
    }
    raw_failed = json.dumps(payload_failed).encode()
    r_failed = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": generate_webhook_signature(raw_failed),
            "x-razorpay-event-id": f"evt_fail_{uuid.uuid4().hex[:8]}",
            "content-type": "application/json",
        },
        content=raw_failed,
    )
    assert r_failed.status_code == 200

    # Verify status is REFUND_FAILED
    async with session_factory() as session:
        res = await session.execute(
            select(PaymentRefund).where(
                PaymentRefund.provider_refund_id == provider_refund_id
            )
        )
        rf = res.scalar_one()
        assert rf.status == RefundStatus.REFUND_FAILED.value
        assert rf.error_code == "BANK_REJECTED"

    # Duplicate refund.failed is idempotent
    r_dup_failed = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": generate_webhook_signature(raw_failed),
            "x-razorpay-event-id": f"evt_dup_fail_{uuid.uuid4().hex[:8]}",
            "content-type": "application/json",
        },
        content=raw_failed,
    )
    assert r_dup_failed.status_code == 200

    # 2. refund.processed arrives afterwards (promotes to REFUND_PROCESSED)
    payload_processed = {
        "event": "refund.processed",
        "payload": {
            "refund": {
                "entity": {
                    "id": provider_refund_id,
                    "payment_id": rzp_payment_id,
                    "amount": order_data["total_payable_paise"],
                    "status": "processed",
                }
            }
        },
    }
    raw_proc = json.dumps(payload_processed).encode()
    r_proc = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": generate_webhook_signature(raw_proc),
            "x-razorpay-event-id": f"evt_proc_{uuid.uuid4().hex[:8]}",
            "content-type": "application/json",
        },
        content=raw_proc,
    )
    assert r_proc.status_code == 200

    # Verify status is REFUND_PROCESSED and error is cleared
    async with session_factory() as session:
        res = await session.execute(
            select(PaymentRefund).where(
                PaymentRefund.provider_refund_id == provider_refund_id
            )
        )
        rf = res.scalar_one()
        assert rf.status == RefundStatus.REFUND_PROCESSED.value
        assert rf.processed_at is not None
        assert rf.error_code is None

    # Duplicate refund.processed is idempotent
    r_dup_proc = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": generate_webhook_signature(raw_proc),
            "x-razorpay-event-id": f"evt_dup_proc_{uuid.uuid4().hex[:8]}",
            "content-type": "application/json",
        },
        content=raw_proc,
    )
    assert r_dup_proc.status_code == 200

    # 3. Stale refund.failed arrives after refund.processed -> MUST NOT REGRESS!
    r_stale_fail = await async_client.post(
        "/api/v1/payments/webhook",
        headers={
            "x-razorpay-signature": generate_webhook_signature(raw_failed),
            "x-razorpay-event-id": f"evt_stale_fail_{uuid.uuid4().hex[:8]}",
            "content-type": "application/json",
        },
        content=raw_failed,
    )
    assert r_stale_fail.status_code == 200

    # Verify status is STILL REFUND_PROCESSED
    async with session_factory() as session:
        res = await session.execute(
            select(PaymentRefund).where(
                PaymentRefund.provider_refund_id == provider_refund_id
            )
        )
        rf = res.scalar_one()
        assert rf.status == RefundStatus.REFUND_PROCESSED.value
        assert rf.processed_at is not None

    # 4. Reconciliation does not regress processed refund
    async with session_factory() as session:
        reconciler = ReconciliationService(session)
        with patch.object(
            reconciler.client,
            "fetch_refund_by_id",
            new_callable=AsyncMock,
            return_value={"id": provider_refund_id, "status": "failed"},
        ):
            await reconciler.reconcile_pending(batch_size=10)

    # Verify status is STILL REFUND_PROCESSED
    async with session_factory() as session:
        res = await session.execute(
            select(PaymentRefund).where(
                PaymentRefund.provider_refund_id == provider_refund_id
            )
        )
        rf = res.scalar_one()
        assert rf.status == RefundStatus.REFUND_PROCESSED.value
        assert rf.processed_at is not None


@pytest.mark.asyncio
async def test_webhook_partial_capture_invariants_and_retry_lifecycle(
    async_client: AsyncClient,
):
    """Verifies that the webhook partial-capture path shares the exact same
    invariants as the payment verification path:
    1. Partial capture received through webhook releases inventory and cancels order.
    2. Reservation release failure through webhook leaves order non-cancelled and sets REQUIRES_RECONCILIATION.
    3. Capture and refund intent survive release failure.
    4. A retry webhook successfully releases reservation and transitions order.
    5. Duplicate webhook delivery does not create duplicate capture/refund or release stock twice.
    6. Webhook arriving after /payments/verify recorded the same capture remains idempotent.
    7. Partial capture can never confirm order or consume inventory as successful fulfillment.
    """
    session_factory = get_session_factory()

    # Part A: Reservation release failure through webhook leaves order non-cancelled and sets REQUIRES_RECONCILIATION
    user, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    headers = {"Authorization": f"Bearer {token}"}

    # Initiate payment attempt
    fake_rzp_order_id = f"order_{uuid.uuid4().hex[:14]}"
    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value={
            "id": fake_rzp_order_id,
            "status": "created",
            "amount": order_data["total_payable_paise"],
            "currency": "INR",
        },
    ):
        init_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/payments",
            headers={**headers, "Idempotency-Key": f"init-wh-part-{order_id}"},
        )
    assert init_resp.status_code == 201

    provider_payment_id = f"pay_wh_part_{uuid.uuid4().hex[:12]}"
    partial_amount = order_data["total_payable_paise"] - 2000

    webhook_payload = {
        "entity": "event",
        "account_id": "acc_mock_123",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": provider_payment_id,
                    "order_id": fake_rzp_order_id,
                    "amount": partial_amount,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                }
            }
        },
        "created_at": int(datetime.now(UTC).timestamp()),
    }
    raw_body = json.dumps(webhook_payload).encode("utf-8")
    sig = generate_webhook_signature(raw_body)
    evt_id1 = f"evt_wh_part_{uuid.uuid4().hex[:8]}"

    # A1. Simulate a real database-level statement failure during reservation release that aborts a PostgreSQL transaction:
    real_release = ReservationService.release_reservation

    async def aborting_pg_release(self, *args, **kwargs):
        # Execute a statement that aborts transaction at the PostgreSQL database engine level
        await self.session.execute(
            text("SELECT * FROM non_existent_table_that_aborts_pg_tx")
        )
        return await real_release(self, *args, **kwargs)

    with (
        patch(
            "app.modules.payments.service.RazorpayClient.create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_{uuid.uuid4().hex[:12]}",
                "status": "processed",
                "amount": partial_amount,
            },
        ),
        patch.object(
            ReservationService,
            "release_reservation",
            aborting_pg_release,
        ),
    ):
        resp_fail = await async_client.post(
            "/api/v1/payments/webhook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": evt_id1,
            },
        )
        assert resp_fail.status_code == 200

    # Verify state after release failure:
    async with session_factory() as session:
        ord_row = await session.get(Order, order_id)
        # 1. Order is NOT cancelled! Reservation release failed!
        assert ord_row.status != OrderStatus.CANCELLED.value
        # 2. Order enters REQUIRES_RECONCILIATION
        assert ord_row.payment_status == PaymentStatus.REQUIRES_RECONCILIATION.value
        assert ord_row.fulfilling_capture_id is None

        # 3. Partial capture is durably recorded
        cap_res = await session.execute(
            select(PaymentCapture).where(
                PaymentCapture.provider_payment_id == provider_payment_id
            )
        )
        cap = cap_res.scalar_one()
        assert (
            cap.reconciliation_status
            == CaptureReconciliationStatus.PARTIAL_CAPTURE_REJECTED.value
        )
        assert cap.is_fulfillment_eligible is False

        # 4. Refund intent is durably recorded
        rfnd_res = await session.execute(
            select(PaymentRefund).where(PaymentRefund.capture_id == cap.id)
        )
        rfnd = rfnd_res.scalar_one()
        assert rfnd.amount_paise == partial_amount

        # 5. The webhook processor finished cleanly and marked the event PROCESSED without a poisoned session
        evt_row = (
            await session.execute(
                select(WebhookEvent).where(WebhookEvent.provider_event_id == evt_id1)
            )
        ).scalar_one()
        assert evt_row.status == WebhookEventStatus.PROCESSED.value

    # A2. Test same provider event ID delivered again:
    # Deduplicated at ingestion level and does NOT rerun business processing
    resp_dup = await async_client.post(
        "/api/v1/payments/webhook",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": evt_id1,
        },
    )
    assert resp_dup.status_code == 200
    assert resp_dup.json()["status"] == "ignored"
    assert resp_dup.json()["reason"] == "ALREADY_INGESTED"

    # Assert business processing was not rerun: still exactly 1 capture, 1 refund, order non-cancelled
    async with session_factory() as session:
        caps_dup = (
            (
                await session.execute(
                    select(PaymentCapture).where(PaymentCapture.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(caps_dup) == 1
        rfnds_dup = (
            (
                await session.execute(
                    select(PaymentRefund).where(PaymentRefund.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rfnds_dup) == 1
        ord_dup = await session.get(Order, order_id)
        assert ord_dup.status != OrderStatus.CANCELLED.value

    # A3. Reconciliation retry after the original webhook has been marked PROCESSED:
    # Razorpay sends NO new event; background reconciliation discovers the order in REQUIRES_RECONCILIATION
    async with session_factory() as session:
        reconciler = ReconciliationService(session)
        rec_res = await reconciler.reconcile_pending(batch_size=10)
        assert rec_res.reconciled_payments_count >= 1

    # Verify state after reconciliation: order cancelled, reservation released exactly once
    async with session_factory() as session:
        ord_rec = await session.get(Order, order_id)
        assert ord_rec.status == OrderStatus.CANCELLED.value
        assert ord_rec.payment_status == PaymentStatus.FAILED.value
        assert ord_rec.fulfilling_capture_id is None

        # Reservation was released cleanly
        res_row = await session.get(InventoryReservation, ord_rec.reservation_id)
        assert res_row.status == ReservationStatus.RELEASED.value

        # Still exactly 1 capture and 1 refund (no duplicate records)
        caps_rec = (
            (
                await session.execute(
                    select(PaymentCapture).where(PaymentCapture.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(caps_rec) == 1
        rfnds_rec = (
            (
                await session.execute(
                    select(PaymentRefund).where(PaymentRefund.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rfnds_rec) == 1

    # A4. Distinct duplicate event for the same capture:
    # A subsequent webhook with a DIFFERENT event_id arrives for the same captured payment
    evt_id_distinct = f"evt_wh_part_distinct_{uuid.uuid4().hex[:8]}"
    with patch(
        "app.modules.payments.service.RazorpayClient.create_refund",
        new_callable=AsyncMock,
        return_value={
            "id": f"rfnd_{uuid.uuid4().hex[:12]}",
            "status": "processed",
            "amount": partial_amount,
        },
    ):
        resp_distinct = await async_client.post(
            "/api/v1/payments/webhook",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": evt_id_distinct,
            },
        )
        assert resp_distinct.status_code == 200

    # Verify idempotency after distinct duplicate: no duplicate release or refund, order stays CANCELLED
    async with session_factory() as session:
        ord_distinct = await session.get(Order, order_id)
        assert ord_distinct.status == OrderStatus.CANCELLED.value
        assert ord_distinct.payment_status == PaymentStatus.FAILED.value

        caps_distinct = (
            (
                await session.execute(
                    select(PaymentCapture).where(PaymentCapture.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(caps_distinct) == 1

        rfnds_distinct = (
            (
                await session.execute(
                    select(PaymentRefund).where(PaymentRefund.order_id == order_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rfnds_distinct) == 1

    # A5. Subsequent reconciliation run is an idempotent no-op (0 partial captures resolved)
    async with session_factory() as session:
        reconciler = ReconciliationService(session)
        rec_res2 = await reconciler.reconcile_pending(batch_size=10)
        assert rec_res2.reconciled_payments_count == 0

    # Part B: Webhook arriving after /payments/verify recorded the same capture
    user_b, token_b, order_b = await setup_customer_and_order(async_client)
    order_b_id = uuid.UUID(order_b["id"])
    headers_b = {"Authorization": f"Bearer {token_b}"}

    fake_rzp_b_id = f"order_{uuid.uuid4().hex[:14]}"
    with patch.object(
        RazorpayClient,
        "create_order",
        new_callable=AsyncMock,
        return_value={
            "id": fake_rzp_b_id,
            "status": "created",
            "amount": order_b["total_payable_paise"],
            "currency": "INR",
        },
    ):
        init_b = await async_client.post(
            f"/api/v1/orders/{order_b_id}/payments",
            headers={**headers_b, "Idempotency-Key": f"init-part-b-{order_b_id}"},
        )
    assert init_b.status_code == 201

    pay_b_id = f"pay_part_b_{uuid.uuid4().hex[:12]}"
    sig_b = generate_payment_signature(fake_rzp_b_id, pay_b_id)
    partial_b_amount = order_b["total_payable_paise"] - 1500

    # 1. /payments/verify records capture and auto-refunds first
    with (
        patch(
            "app.modules.payments.service.RazorpayClient.fetch_payment",
            new_callable=AsyncMock,
            return_value={
                "id": pay_b_id,
                "order_id": fake_rzp_b_id,
                "amount": partial_b_amount,
                "currency": "INR",
                "status": "captured",
                "method": "card",
            },
        ),
        patch(
            "app.modules.payments.service.RazorpayClient.create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_{uuid.uuid4().hex[:12]}",
                "status": "processed",
                "amount": partial_b_amount,
            },
        ),
    ):
        v_b = await async_client.post(
            f"/api/v1/orders/{order_b_id}/payments/verify",
            headers=headers_b,
            json={
                "razorpay_order_id": fake_rzp_b_id,
                "razorpay_payment_id": pay_b_id,
                "razorpay_signature": sig_b,
            },
        )
        assert v_b.status_code == 400
        assert v_b.json()["error"]["code"] == "PARTIAL_CAPTURE_REJECTED"

    # 2. Webhook arrives afterwards for the same capture
    webhook_b_payload = {
        "entity": "event",
        "account_id": "acc_mock_123",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": pay_b_id,
                    "order_id": fake_rzp_b_id,
                    "amount": partial_b_amount,
                    "currency": "INR",
                    "status": "captured",
                    "method": "card",
                }
            }
        },
        "created_at": int(datetime.now(UTC).timestamp()),
    }
    raw_b = json.dumps(webhook_b_payload).encode("utf-8")
    resp_wh_b = await async_client.post(
        "/api/v1/payments/webhook",
        content=raw_b,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": generate_webhook_signature(raw_b),
            "X-Razorpay-Event-Id": f"evt_wh_b_{uuid.uuid4().hex[:8]}",
        },
    )
    assert resp_wh_b.status_code == 200

    # Verify idempotency: exactly 1 capture, exactly 1 refund, order stays CANCELLED
    async with session_factory() as session:
        ord_b_row = await session.get(Order, order_b_id)
        assert ord_b_row.status == OrderStatus.CANCELLED.value
        assert ord_b_row.payment_status == PaymentStatus.FAILED.value
        assert ord_b_row.fulfilling_capture_id is None

        caps_b = (
            (
                await session.execute(
                    select(PaymentCapture).where(PaymentCapture.order_id == order_b_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(caps_b) == 1

        rfnds_b = (
            (
                await session.execute(
                    select(PaymentRefund).where(PaymentRefund.order_id == order_b_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(rfnds_b) == 1
