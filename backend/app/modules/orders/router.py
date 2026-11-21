import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.cart.dependencies import (
    GUEST_CART_COOKIE_NAME,
    ensure_can_shop,
    get_current_user_optional,
)
from app.modules.identity.dependencies import (
    require_admin_or_internal_service,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.orders.models import PaymentStatus
from app.modules.orders.schemas import (
    CreateOrderRequest,
    CreateShipmentRequest,
    GuestOrderLookupRequest,
    NotificationListResponse,
    OrderCancellationRequest,
    OrderCancellationResponse,
    OrderListResponse,
    OrderResponse,
    OrderTrackingResponse,
    ReturnCreateRequest,
    ReturnResponse,
    ReturnStatusUpdateRequest,
    ShipmentResponse,
    UpdateShipmentStatusRequest,
)
from app.modules.orders.service import OrderService

router = APIRouter(tags=["orders"], dependencies=[Depends(verify_csrf_token)])


def _extract_ownership_identifiers(
    request: Request,
    user: User | None,
) -> tuple[uuid.UUID | None, str | None, str | None]:
    customer_id = user.id if user else None
    guest_token_hash = None
    guest_access_token = request.headers.get(
        "X-Guest-Access-Token"
    ) or request.query_params.get("access_token")
    if not customer_id:
        guest_token = request.cookies.get(
            GUEST_CART_COOKIE_NAME
        ) or request.headers.get("X-Guest-Cart-Token")
        if guest_token:
            guest_token_hash = hashlib.sha256(guest_token.encode()).hexdigest()
    return customer_id, guest_token_hash, guest_access_token


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order from active quote and reservation",
)
async def create_order(
    payload: CreateOrderRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderResponse:
    user = await get_current_user_optional(request, db)
    ensure_can_shop(user)
    customer_id, guest_token_hash, _ = _extract_ownership_identifiers(request, user)

    effective_key = idempotency_key or payload.idempotency_key
    if effective_key:
        payload.idempotency_key = effective_key

    service = OrderService(db)
    order = await service.create_order(
        req=payload,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return OrderResponse.model_validate(order)


@router.get(
    "/orders",
    response_model=OrderListResponse,
    summary="List orders for current authenticated customer or guest with search/filters",
)
async def list_orders(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    from_date: Annotated[datetime | None, Query(alias="from_date")] = None,
    to_date: Annotated[datetime | None, Query(alias="to_date")] = None,
    search: Annotated[str | None, Query(alias="search")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, _ = _extract_ownership_identifiers(request, user)

    eff_skip = skip or offset
    service = OrderService(db)
    items, total = await service.list_orders(
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        status=status_filter,
        from_date=from_date,
        to_date=to_date,
        search=search,
        skip=eff_skip,
        limit=limit,
    )
    return OrderListResponse(items=items, total=total)


@router.post(
    "/orders/guest-lookup",
    response_model=OrderResponse,
    summary="Look up order using guest access token",
)
async def guest_order_lookup(
    payload: GuestOrderLookupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    service = OrderService(db)
    order = await service.guest_order_lookup(
        order_number=payload.order_number,
        access_token=payload.access_token,
    )
    return OrderResponse.model_validate(order)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Retrieve order by ID with tenant ownership enforcement",
)
async def get_order(
    order_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Query(alias="access_token")] = None,
) -> OrderResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, header_access_token = _extract_ownership_identifiers(
        request, user
    )
    eff_access_token = access_token or header_access_token

    service = OrderService(db)
    order = await service.get_order(
        order_id=order_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        guest_access_token=eff_access_token,
    )
    return OrderResponse.model_validate(order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderCancellationResponse,
    summary="Cancel order before shipment",
)
async def cancel_order(
    order_id: uuid.UUID,
    payload: OrderCancellationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> OrderCancellationResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, guest_access_token = _extract_ownership_identifiers(
        request, user
    )

    effective_key = idempotency_key or payload.idempotency_key
    service = OrderService(db)
    order = await service.cancel_order(
        order_id=order_id,
        reason=payload.reason,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        guest_access_token=guest_access_token,
        idempotency_key=effective_key,
    )
    return OrderCancellationResponse(
        order_id=order.id,
        order_number=order.order_number,
        status=order.status,
        cancelled_at=order.cancelled_at or datetime.now(UTC),
        refund_status="REFUNDED"
        if order.payment_status == PaymentStatus.REFUNDED.value
        else None,
        refund_amount_paise=order.total_payable_paise
        if order.payment_status == PaymentStatus.REFUNDED.value
        else None,
        inventory_restocked=True,
        message="Order successfully cancelled.",
    )


@router.get(
    "/orders/{order_id}/tracking",
    response_model=OrderTrackingResponse,
    summary="Retrieve complete order tracking timeline and carrier events",
)
async def get_order_tracking(
    order_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Query(alias="access_token")] = None,
) -> OrderTrackingResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, header_access_token = _extract_ownership_identifiers(
        request, user
    )
    eff_access_token = access_token or header_access_token

    service = OrderService(db)
    return await service.get_order_tracking(
        order_id=order_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        guest_access_token=eff_access_token,
    )


@router.post(
    "/orders/{order_id}/shipments",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create shipment for order (admin / internal fulfilment only)",
)
async def create_shipment(
    order_id: uuid.UUID,
    payload: CreateShipmentRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _actor: Annotated[str, Depends(require_admin_or_internal_service)],
) -> ShipmentResponse:
    service = OrderService(db)
    shipment = await service.create_shipment(
        order_id=order_id,
        req=payload,
    )
    return ShipmentResponse.model_validate(shipment)


@router.patch(
    "/orders/{order_id}/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    summary="Update shipment status and tracking details (admin / internal only)",
)
async def update_shipment_status(
    order_id: uuid.UUID,
    shipment_id: uuid.UUID,
    payload: UpdateShipmentStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _actor: Annotated[str, Depends(require_admin_or_internal_service)],
) -> ShipmentResponse:
    service = OrderService(db)
    shipment = await service.update_shipment_status(
        order_id=order_id,
        shipment_id=shipment_id,
        req=payload,
    )
    return ShipmentResponse.model_validate(shipment)


@router.post(
    "/orders/{order_id}/returns",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request a return for delivered order items",
)
async def request_return(
    order_id: uuid.UUID,
    payload: ReturnCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReturnResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, guest_access_token = _extract_ownership_identifiers(
        request, user
    )

    if idempotency_key:
        payload.idempotency_key = idempotency_key

    service = OrderService(db)
    ret = await service.request_return(
        order_id=order_id,
        req=payload,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        guest_access_token=guest_access_token,
    )
    return ReturnResponse.model_validate(ret)


@router.get(
    "/orders/{order_id}/returns",
    response_model=list[ReturnResponse],
    summary="List returns requested for an order",
)
async def list_order_returns(
    order_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    access_token: Annotated[str | None, Query(alias="access_token")] = None,
) -> list[ReturnResponse]:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, header_access_token = _extract_ownership_identifiers(
        request, user
    )
    eff_access_token = access_token or header_access_token

    service = OrderService(db)
    returns = await service.list_returns_for_order(
        order_id=order_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        guest_access_token=eff_access_token,
    )
    return [ReturnResponse.model_validate(r) for r in returns]


@router.patch(
    "/returns/{return_id}/status",
    response_model=ReturnResponse,
    summary="Update return lifecycle status (admin / internal only)",
)
async def update_return_status(
    return_id: uuid.UUID,
    payload: ReturnStatusUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[str, Depends(require_admin_or_internal_service)],
) -> ReturnResponse:
    service = OrderService(db)
    ret = await service.update_return_status(
        return_id=return_id,
        req=payload,
        actor=actor,
    )
    return ReturnResponse.model_validate(ret)


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="List in-app customer notifications",
)
async def list_notifications(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> NotificationListResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, _ = _extract_ownership_identifiers(request, user)

    service = OrderService(db)
    items, total = await service.list_notifications(
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        skip=skip,
        limit=limit,
    )
    unread = await service.get_unread_notification_count(
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return NotificationListResponse(items=items, unread_count=unread)


@router.get(
    "/notifications/unread-count",
    summary="Get unread notifications count badge",
)
async def get_unread_count(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, _ = _extract_ownership_identifiers(request, user)

    service = OrderService(db)
    count = await service.get_unread_notification_count(
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return {"unread_count": count}


@router.post(
    "/notifications/{notification_id}/read",
    summary="Mark a specific notification as read",
)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, bool]:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash, _ = _extract_ownership_identifiers(request, user)

    service = OrderService(db)
    success = await service.mark_notification_as_read(
        notification_id=notification_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return {"success": success}
