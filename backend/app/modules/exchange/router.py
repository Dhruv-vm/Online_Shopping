import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.exchange.schemas import (
    AcceptBidRequest,
    AcceptBidResponse,
    BidItem,
    BidSubmitRequest,
    ExchangeRequestCreate,
    ExchangeRequestItem,
    ExchangeRequestList,
)
from app.modules.exchange.service import ExchangeService
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_admin,
    require_retailer,
    require_role,
    verify_csrf_token,
)
from app.modules.identity.models import User

require_customer = require_role("customer")

router = APIRouter(
    prefix="/exchange",
    tags=["Community Exchange"],
    dependencies=[Depends(verify_csrf_token)],
)
retailer_router = APIRouter(
    prefix="/retailer/exchange",
    tags=["Community Exchange (Retailer)"],
    dependencies=[Depends(require_retailer), Depends(verify_csrf_token)],
)
admin_router = APIRouter(
    prefix="/admin/exchange",
    tags=["Community Exchange (Admin)"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


@router.post("/requests", response_model=ExchangeRequestItem, status_code=201)
async def create_rfq(
    payload: ExchangeRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> ExchangeRequestItem:
    svc = ExchangeService(db)
    return (
        await svc.serialize(
            [await svc.create_request(user.id, payload)], include_bids=True
        )
    )[0]


@router.get("/requests", response_model=ExchangeRequestList)
async def my_rfqs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExchangeRequestList:
    svc = ExchangeService(db)
    items, total = await svc.list_for_customer(user.id, limit, offset)
    return ExchangeRequestList(
        items=await svc.serialize(items, include_bids=True), total=total
    )


@router.get("/requests/{request_id}", response_model=ExchangeRequestItem)
async def get_rfq(
    request_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> ExchangeRequestItem:
    svc = ExchangeService(db)
    return (
        await svc.serialize([await svc.get_own(request_id, user.id)], include_bids=True)
    )[0]


@router.post("/requests/{request_id}/accept-bid", response_model=AcceptBidResponse)
async def accept_bid(
    request_id: uuid.UUID,
    payload: AcceptBidRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> AcceptBidResponse:
    """Accept a bid: bid prices are locked as price awards and the lines are put
    in the customer's cart; complete purchase through normal checkout."""
    svc = ExchangeService(db)
    r, cart, n = await svc.accept_bid(request_id, user.id, payload.bid_id)
    return AcceptBidResponse(
        request=(await svc.serialize([r], include_bids=True))[0],
        cart_id=cart.id,
        awarded_lines=n,
        message="Offer accepted. The items are in your basket at the agreed prices for 48 hours.",
    )


@router.post("/requests/{request_id}/cancel", response_model=ExchangeRequestItem)
async def cancel_rfq(
    request_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> ExchangeRequestItem:
    svc = ExchangeService(db)
    return (
        await svc.serialize([await svc.cancel(request_id, user.id)], include_bids=True)
    )[0]


@retailer_router.get("/requests", response_model=ExchangeRequestList)
async def retailer_open_rfqs(
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExchangeRequestList:
    svc = ExchangeService(db)
    items, total = await svc.open_for_retailer(retailer, limit=limit, offset=offset)
    return ExchangeRequestList(
        items=await svc.serialize(items, retailer_id=retailer.id), total=total
    )


@retailer_router.post(
    "/requests/{request_id}/bids", response_model=BidItem, status_code=201
)
async def retailer_submit_bid(
    request_id: uuid.UUID,
    payload: BidSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> BidItem:
    """Submit or revise this store's bid (one bid per retailer per request)."""
    svc = ExchangeService(db)
    await svc.submit_bid(request_id, retailer, payload)
    from app.modules.exchange.models import ExchangeRequest

    r = await db.get(ExchangeRequest, request_id)
    return (await svc.serialize([r], retailer_id=retailer.id))[0].my_bid


@retailer_router.delete("/requests/{request_id}/bids", status_code=204)
async def retailer_withdraw_bid(
    request_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> None:
    await ExchangeService(db).withdraw_bid(request_id, retailer)


@admin_router.get("/requests", response_model=ExchangeRequestList)
async def admin_rfqs(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["BIDDING_OPEN", "AWARDED", "EXPIRED", "CANCELLED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExchangeRequestList:
    svc = ExchangeService(db)
    items, total = await svc.list_admin(status, limit, offset)
    return ExchangeRequestList(
        items=await svc.serialize(items, include_bids=True), total=total
    )


class ModerationRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=300)


@admin_router.post("/requests/{request_id}/cancel", response_model=ExchangeRequestItem)
async def admin_moderate_rfq(
    request_id: uuid.UUID,
    payload: ModerationRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExchangeRequestItem:
    """Admin: close an abusive or invalid RFQ (customer is notified)."""
    svc = ExchangeService(db)
    from app.modules.governance.audit import record_audit_details

    record_audit_details(request, action="cancel_rfq", reason=payload.reason)
    r = await svc.moderate_cancel(request_id, payload.reason)
    return (await svc.serialize([r], include_bids=True))[0]
