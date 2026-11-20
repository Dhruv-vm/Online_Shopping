import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.pincode import validate_pincode
from app.modules.cart.dependencies import get_current_user_optional
from app.modules.catalogue.models import Retailer
from app.modules.demand.schemas import (
    AdminDemandPoolUpdate,
    DemandFulfillRequest,
    DemandJoinRequest,
    DemandPoolItem,
    DemandPoolListResponse,
    DemandSignalRequest,
    DemandSignalResponse,
    DemandTrendsResponse,
)
from app.modules.demand.service import DemandService, caller_identity
from app.modules.identity.dependencies import (
    get_current_retailer,
    get_current_user,
    require_admin,
    require_retailer,
    verify_csrf_token,
)
from app.modules.identity.models import User

router = APIRouter(
    prefix="/demand", tags=["Demand Gap"], dependencies=[Depends(verify_csrf_token)]
)
retailer_router = APIRouter(
    prefix="/retailer/demand-gaps",
    tags=["Demand Gap (Retailer)"],
    dependencies=[Depends(require_retailer), Depends(verify_csrf_token)],
)
admin_router = APIRouter(
    prefix="/admin/demand",
    tags=["Demand Gap (Admin)"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


def _customers_only(user) -> None:
    """Retailers/admins must not cast demand signals (market manipulation)."""
    if user is not None and user.role != "customer":
        from app.core.exceptions import AppException

        raise AppException(
            code="FORBIDDEN",
            message="Only customers can request products.",
            status_code=403,
        )


def _pin(p: str | None) -> str | None:
    try:
        return validate_pincode(p)
    except ValueError as exc:
        from app.core.exceptions import AppException

        raise AppException(
            code="INVALID_PINCODE", message=str(exc), status_code=422
        ) from None


@router.post("/signal", response_model=DemandSignalResponse, status_code=201)
async def log_demand_signal(
    payload: DemandSignalRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DemandSignalResponse:
    """Public (customer or guest): request a product / notify me / out-of-stock."""
    user = await get_current_user_optional(request, db)
    _customers_only(user)
    uid, guest = caller_identity(request, user)
    svc = DemandService(db)
    pool, dedup = await svc.record_signal(
        signal_type=payload.signal_type,
        query_text=payload.query_text,
        listing_id=payload.listing_id,
        category_id=payload.category_id,
        pincode=payload.pincode,
        user_id=uid,
        guest_token_hash=guest,
    )
    return DemandSignalResponse(
        pool=(await svc.serialize([pool], with_offers=False))[0], deduplicated=dedup
    )


@router.post(
    "/pools/{pool_id}/join", response_model=DemandSignalResponse, status_code=201
)
async def join_demand_pool(
    pool_id: uuid.UUID,
    payload: DemandJoinRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DemandSignalResponse:
    user = await get_current_user_optional(request, db)
    _customers_only(user)
    uid, guest = caller_identity(request, user)
    svc = DemandService(db)
    pool, dedup = await svc.record_signal(
        signal_type="WISHLIST",
        query_text=None,
        pincode=payload.pincode,
        user_id=uid,
        guest_token_hash=guest,
        pool_id=pool_id,
    )
    return DemandSignalResponse(
        pool=(await svc.serialize([pool], with_offers=False))[0], deduplicated=dedup
    )


@router.get("/pools", response_model=DemandPoolListResponse)
async def browse_demand_pools(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    pincode: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DemandPoolListResponse:
    """Public: similar open demand (aggregate counts only, no customer identities)."""
    svc = DemandService(db)
    pools, total = await svc.search_pools(
        q=q, pincode=_pin(pincode), limit=limit, offset=offset
    )
    return DemandPoolListResponse(
        items=await svc.serialize(pools, with_offers=False), total=total
    )


@router.get("/my-requests", response_model=DemandPoolListResponse)
async def my_demand_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DemandPoolListResponse:
    svc = DemandService(db)
    pools = await svc.my_pools(user.id)
    return DemandPoolListResponse(items=await svc.serialize(pools), total=len(pools))


@retailer_router.get("", response_model=DemandPoolListResponse)
async def retailer_demand_gaps(
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    pincode: str | None = None,
    category_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DemandPoolListResponse:
    svc = DemandService(db)
    pools, total = await svc.retailer_gaps(
        retailer,
        pincode=_pin(pincode),
        category_id=category_id,
        limit=limit,
        offset=offset,
    )
    return DemandPoolListResponse(
        items=await svc.serialize(pools, retailer_id=retailer.id), total=total
    )


@retailer_router.post("/{pool_id}/fulfill", response_model=DemandPoolItem)
async def retailer_fulfill_demand(
    pool_id: uuid.UUID,
    payload: DemandFulfillRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> DemandPoolItem:
    svc = DemandService(db)
    pool = await svc.fulfill(retailer, pool_id, payload.listing_id, payload.note)
    return (await svc.serialize([pool], retailer_id=retailer.id))[0]


@admin_router.get("/pools", response_model=DemandPoolListResponse)
async def admin_demand_pools(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["OPEN", "FULFILLED", "EXPIRED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DemandPoolListResponse:
    svc = DemandService(db)
    pools, total = await svc.admin_list(status=status, limit=limit, offset=offset)
    return DemandPoolListResponse(items=await svc.serialize(pools), total=total)


@admin_router.patch("/pools/{pool_id}", response_model=DemandPoolItem)
async def admin_update_demand_pool(
    pool_id: uuid.UUID,
    payload: AdminDemandPoolUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DemandPoolItem:
    svc = DemandService(db)
    pool = await svc.admin_update(
        pool_id, status=payload.status, threshold=payload.visibility_threshold
    )
    return (await svc.serialize([pool]))[0]


@admin_router.get("/trends", response_model=DemandTrendsResponse)
async def admin_demand_trends(
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> DemandTrendsResponse:
    return await DemandService(db).trends(days)
