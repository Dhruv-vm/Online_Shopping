import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.cart.dependencies import (
    GUEST_CART_COOKIE_NAME,
    get_current_user_optional,
)
from app.modules.identity.models import User
from app.modules.orders.schemas import (
    CreateOrderRequest,
    OrderListResponse,
    OrderResponse,
)
from app.modules.orders.service import OrderService

router = APIRouter(tags=["orders"])


def _extract_ownership_identifiers(
    request: Request,
    user: User | None,
) -> tuple[uuid.UUID | None, str | None]:
    customer_id = user.id if user else None
    guest_token_hash = None
    if not customer_id:
        guest_token = request.cookies.get(
            GUEST_CART_COOKIE_NAME
        ) or request.headers.get("X-Guest-Cart-Token")
        if guest_token:
            guest_token_hash = hashlib.sha256(guest_token.encode()).hexdigest()
    return customer_id, guest_token_hash


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
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

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
    summary="List orders for current authenticated customer or guest",
)
async def list_orders(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OrderListResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = OrderService(db)
    items, total = await service.list_orders(
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        skip=skip,
        limit=limit,
    )
    return OrderListResponse(items=items, total=total)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Retrieve order by ID with tenant ownership enforcement",
)
async def get_order(
    order_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = OrderService(db)
    order = await service.get_order(
        order_id=order_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return OrderResponse.model_validate(order)
