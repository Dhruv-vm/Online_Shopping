import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.database import get_session_factory
from app.modules.orders.models import (
    Order,
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    ShipmentStatus,
)
from app.modules.payments.client import RazorpayClient
from tests.test_orders import (
    generate_payment_signature,
    get_test_listing,
    setup_customer_and_order,
)


@pytest.mark.asyncio
async def test_guest_order_creation_and_guest_lookup(async_client: AsyncClient):
    """Guest checkout receives an unguessable access_token and can look up their order."""
    listing = await get_test_listing(async_client, min_stock=10)
    listing_id = uuid.UUID(listing["id"])
    guest_cookie = f"guest_cart_{uuid.uuid4().hex}"
    async_client.cookies.set("guest_cart_token", guest_cookie)

    # 1. Add to cart & quote
    await async_client.post(
        "/api/v1/cart/items",
        json={"listing_id": str(listing_id), "quantity": 1},
    )
    q_resp = await async_client.post(
        "/api/v1/quotes",
        json={
            "delivery_address": {
                "full_name": "Guest Customer",
                "address_line1": "123 Guest Street",
                "city": "Bengaluru",
                "state": "KA",
                "postal_code": "560001",
                "phone": "+919876543210",
            }
        },
    )
    assert q_resp.status_code == 201
    quote_id = q_resp.json()["id"]

    # 2. Reservation
    r_resp = await async_client.post(
        "/api/v1/reservations", json={"quote_id": quote_id}
    )
    assert r_resp.status_code == 201
    res_id = r_resp.json()["id"]

    # 3. Create order
    order_resp = await async_client.post(
        "/api/v1/orders",
        json={"quote_id": quote_id, "reservation_id": res_id},
    )
    assert order_resp.status_code == 201
    order_data = order_resp.json()
    assert order_data["guest_access_token"] is not None
    access_token = order_data["guest_access_token"]
    order_number = order_data["order_number"]

    # 4. Lookup order using valid access token
    lookup_resp = await async_client.post(
        "/api/v1/orders/guest-lookup",
        json={"order_number": order_number, "access_token": access_token},
    )
    assert lookup_resp.status_code == 200
    assert lookup_resp.json()["id"] == order_data["id"]

    # 5. Lookup fails with invalid access token
    bad_lookup = await async_client.post(
        "/api/v1/orders/guest-lookup",
        json={"order_number": order_number, "access_token": "wrong_token_1234567890"},
    )
    assert bad_lookup.status_code == 404


@pytest.mark.asyncio
async def test_order_cancellation_pre_payment_releases_hold(async_client: AsyncClient):
    """Cancelling an unpaid order transitions to CANCELLED and releases the inventory hold."""
    user, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])

    cancel_resp = await async_client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "Customer changed mind"},
    )
    assert cancel_resp.status_code == 200
    cancel_data = cancel_resp.json()
    assert cancel_data["status"] == OrderStatus.CANCELLED.value
    assert cancel_data["inventory_restocked"] is True

    # Check order status in DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        assert db_order.status == OrderStatus.CANCELLED.value
        assert db_order.cancellation_reason == "Customer changed mind"


@pytest.mark.asyncio
async def test_order_cancellation_post_payment_restocks_and_refunds(
    async_client: AsyncClient,
):
    """Cancelling a confirmed order restocks on_hand inventory and initiates a refund."""
    user, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    amount = order_data["total_payable_paise"]

    # Confirm order via payment verification
    provider_order_id = f"order_rzp_{uuid.uuid4().hex[:8]}"
    provider_payment_id = f"pay_rzp_{uuid.uuid4().hex[:8]}"
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
                "receipt": order_data["order_number"],
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
        patch.object(
            RazorpayClient,
            "create_refund",
            new_callable=AsyncMock,
            return_value={
                "id": f"rfnd_{uuid.uuid4().hex[:8]}",
                "amount": amount,
                "status": "processed",
            },
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

        cancel_resp = await async_client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Customer found better price"},
        )
        assert cancel_resp.status_code == 200
        cancel_data = cancel_resp.json()
        assert cancel_data["status"] == OrderStatus.CANCELLED.value
        assert cancel_data["refund_status"] is not None


@pytest.mark.asyncio
async def test_order_fulfillment_shipment_and_tracking(async_client: AsyncClient):
    """Creating a shipment advances the order status to SHIPPED and tracks carrier events."""
    user, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    session_factory = get_session_factory()

    # Move order to CONFIRMED
    async with session_factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        order.status = OrderStatus.CONFIRMED.value
        await session.commit()

    # 1. Create shipment
    ship_resp = await async_client.post(
        f"/api/v1/orders/{order_id}/shipments",
        json={
            "carrier_name": "Delhivery",
            "carrier_code": "DELHIVERY",
            "tracking_number": "DEL123456789",
        },
    )
    assert ship_resp.status_code == 201
    ship_data = ship_resp.json()
    assert ship_data["tracking_number"] == "DEL123456789"
    assert "delhivery.com" in ship_data["tracking_url"]
    shipment_id = ship_data["id"]

    # 2. Get tracking timeline
    track_resp = await async_client.get(f"/api/v1/orders/{order_id}/tracking")
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert track_data["order_status"] == OrderStatus.SHIPPED.value
    assert len(track_data["timeline"]) > 0

    # Shipped order CANNOT be cancelled
    bad_cancel = await async_client.post(
        f"/api/v1/orders/{order_id}/cancel",
        json={"reason": "Too late to cancel"},
    )
    assert bad_cancel.status_code == 400
    assert "ORDER_CANNOT_BE_CANCELLED" in bad_cancel.text

    # 3. Update shipment status to OUT_FOR_DELIVERY then DELIVERED
    update_resp1 = await async_client.patch(
        f"/api/v1/orders/{order_id}/shipments/{shipment_id}",
        json={"status": ShipmentStatus.OUT_FOR_DELIVERY.value, "location": "Local Hub"},
    )
    assert update_resp1.status_code == 200
    assert update_resp1.json()["status"] == ShipmentStatus.OUT_FOR_DELIVERY.value

    update_resp2 = await async_client.patch(
        f"/api/v1/orders/{order_id}/shipments/{shipment_id}",
        json={
            "status": ShipmentStatus.DELIVERED.value,
            "location": "Customer Doorstep",
        },
    )
    assert update_resp2.status_code == 200

    # Verify order is now DELIVERED
    order_check = await async_client.get(f"/api/v1/orders/{order_id}")
    assert order_check.json()["status"] == OrderStatus.DELIVERED.value
    assert order_check.json()["delivered_at"] is not None


@pytest.mark.asyncio
async def test_order_return_lifecycle(async_client: AsyncClient):
    """Delivered order can be returned, inspected, restocked, and refunded."""
    user, token, order_data = await setup_customer_and_order(async_client)
    order_id = uuid.UUID(order_data["id"])
    item_id = order_data["items"][0]["id"]
    session_factory = get_session_factory()

    # Move order to DELIVERED
    now = datetime.now(UTC)
    async with session_factory() as session:
        order = (
            await session.execute(select(Order).where(Order.id == order_id))
        ).scalar_one()
        order.status = OrderStatus.DELIVERED.value
        order.delivered_at = now - timedelta(days=2)  # within 15 days window
        order.payment_status = PaymentStatus.SUCCEEDED.value
        await session.commit()

    # 1. Request return
    ret_resp = await async_client.post(
        f"/api/v1/orders/{order_id}/returns",
        json={
            "reason": "Defective item",
            "customer_notes": "Item arrived with cosmetic damage",
            "items": [{"order_item_id": item_id, "quantity": 1}],
        },
    )
    assert ret_resp.status_code == 201
    ret_data = ret_resp.json()
    assert ret_data["status"] == ReturnStatus.REQUESTED.value
    return_id = ret_data["id"]

    # 2. Inspect return and approve restock
    inspect_resp = await async_client.patch(
        f"/api/v1/returns/{return_id}/status",
        json={
            "status": ReturnStatus.INSPECTED.value,
            "restock_approved": True,
            "admin_notes": "Verified good condition",
        },
    )
    assert inspect_resp.status_code == 200
    assert inspect_resp.json()["status"] == ReturnStatus.INSPECTED.value

    # 3. Process refund
    with patch.object(
        RazorpayClient,
        "create_refund",
        new_callable=AsyncMock,
        return_value={
            "id": f"rfnd_{uuid.uuid4().hex[:8]}",
            "amount": ret_data["refund_amount_paise"],
            "status": "processed",
        },
    ):
        refund_resp = await async_client.patch(
            f"/api/v1/returns/{return_id}/status",
            json={
                "status": ReturnStatus.REFUNDED.value,
                "admin_notes": "Refund authorized",
            },
        )
        assert refund_resp.status_code == 200
        assert refund_resp.json()["status"] == ReturnStatus.REFUNDED.value


@pytest.mark.asyncio
async def test_customer_notification_center(async_client: AsyncClient):
    """Customer can view notifications, check unread counts, and mark as read."""
    user, token, order_data = await setup_customer_and_order(async_client)

    # List notifications
    notif_resp = await async_client.get("/api/v1/notifications")
    assert notif_resp.status_code == 200
    notif_data = notif_resp.json()
    assert notif_data["unread_count"] >= 1
    first_notif = notif_data["items"][0]

    # Check unread badge count
    count_resp = await async_client.get("/api/v1/notifications/unread-count")
    assert count_resp.status_code == 200
    assert count_resp.json()["unread_count"] >= 1

    # Mark as read
    read_resp = await async_client.post(
        f"/api/v1/notifications/{first_notif['id']}/read"
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["success"] is True
