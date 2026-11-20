import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.cart.dependencies import (
    GUEST_CART_COOKIE_NAME,
    get_current_user_optional,
)
from app.modules.identity.dependencies import verify_csrf_token
from app.modules.identity.models import User
from app.modules.inventory.dependencies import verify_internal_service_key
from app.modules.inventory.schemas import (
    CreateReservationRequest,
    ReservationCleanupResponse,
    ReservationReleaseResponse,
    ReservationResponse,
)
from app.modules.inventory.service import ReservationService

router = APIRouter(
    tags=["inventory-reservations"], dependencies=[Depends(verify_csrf_token)]
)
# Service-to-service endpoints authenticate with X-Internal-Service-Key, never
# with browser cookies, so they are kept off the CSRF-protected router.
internal_router = APIRouter(tags=["inventory-reservations-internal"])


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
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create atomic inventory reservation from an active checkout quote",
)
async def create_reservation(
    payload: CreateReservationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReservationResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    effective_idempotency_key = idempotency_key or payload.idempotency_key

    service = ReservationService(db)
    reservation = await service.create_reservation_from_quote(
        quote_id=payload.quote_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        idempotency_key=effective_idempotency_key,
    )
    return ReservationResponse.from_orm_model(reservation)


@router.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    summary="Get reservation status, items, and countdown seconds remaining",
)
async def get_reservation(
    reservation_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReservationResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = ReservationService(db)
    reservation = await service.get_reservation(
        reservation_id=reservation_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
    )
    return ReservationResponse.from_orm_model(reservation)


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=ReservationReleaseResponse,
    summary="Explicitly release an active inventory reservation",
)
async def release_reservation(
    reservation_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReservationReleaseResponse:
    user = await get_current_user_optional(request, db)
    customer_id, guest_token_hash = _extract_ownership_identifiers(request, user)

    service = ReservationService(db)
    reservation = await service.release_reservation(
        reservation_id=reservation_id,
        customer_id=customer_id,
        guest_token_hash=guest_token_hash,
        reason="USER_RELEASED",
    )
    return ReservationReleaseResponse(
        id=reservation.id,
        status=reservation.status,
        released_at=reservation.released_at,
        release_reason=reservation.release_reason,
    )


@internal_router.post(
    "/internal/reservations/cleanup-expired",
    response_model=ReservationCleanupResponse,
    summary="Internal cleanup endpoint to expire reservations past TTL and restore stock",
    dependencies=[Depends(verify_internal_service_key)],
)
async def cleanup_expired_reservations(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReservationCleanupResponse:
    service = ReservationService(db)
    count = await service.cleanup_expired_reservations()
    return ReservationCleanupResponse(
        expired_count=count,
        timestamp=datetime.now(UTC),
    )
