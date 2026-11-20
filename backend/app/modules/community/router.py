import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.cart.dependencies import get_current_user_optional
from app.modules.catalogue.models import Retailer
from app.modules.community.schemas import (
    CampaignCreateRequest,
    CampaignItem,
    CampaignListResponse,
    JoinRequest,
    ShareResponse,
)
from app.modules.community.service import CommunityBuyingService
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
    prefix="/community-buying",
    tags=["Community Buying"],
    dependencies=[Depends(verify_csrf_token)],
)
retailer_router = APIRouter(
    prefix="/retailer/community-buying",
    tags=["Community Buying (Retailer)"],
    dependencies=[Depends(require_retailer), Depends(verify_csrf_token)],
)
admin_router = APIRouter(
    prefix="/admin/community-buying",
    tags=["Community Buying (Admin)"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


async def _one(svc: CommunityBuyingService, c, uid=None) -> CampaignItem:
    return (await svc.serialize([c], uid))[0]


@router.get("/campaigns", response_model=CampaignListResponse)
async def browse_campaigns(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CampaignListResponse:
    """Public: active group pools with progress and countdown."""
    user = await get_current_user_optional(request, db)
    svc = CommunityBuyingService(db)
    items, total = await svc.list(
        status="OPEN", retailer_id=None, limit=limit, offset=offset
    )
    return CampaignListResponse(
        items=await svc.serialize(items, user.id if user else None), total=total
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignItem)
async def get_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignItem:
    user = await get_current_user_optional(request, db)
    svc = CommunityBuyingService(db)
    return await _one(svc, await svc.get(campaign_id), user.id if user else None)


@router.post("/campaigns/{campaign_id}/join", response_model=CampaignItem)
async def join_campaign(
    campaign_id: uuid.UUID,
    payload: JoinRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> CampaignItem:
    """Customer: join the pool. No payment is taken now; members pay the unlocked
    group price at normal checkout after the campaign succeeds."""
    svc = CommunityBuyingService(db)
    return await _one(
        svc, await svc.join(campaign_id, user.id, payload.quantity), user.id
    )


@router.post("/campaigns/{campaign_id}/leave", response_model=CampaignItem)
async def leave_campaign(
    campaign_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> CampaignItem:
    svc = CommunityBuyingService(db)
    return await _one(svc, await svc.leave(campaign_id, user.id), user.id)


@router.get("/campaigns/{campaign_id}/share", response_model=ShareResponse)
async def share_campaign(
    campaign_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> ShareResponse:
    return await CommunityBuyingService(db).share(campaign_id, user.id)


@retailer_router.get("/campaigns", response_model=CampaignListResponse)
async def retailer_campaigns(
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    status: Literal["OPEN", "SUCCESSFUL", "FAILED", "CANCELLED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CampaignListResponse:
    svc = CommunityBuyingService(db)
    items, total = await svc.list(
        status=status, retailer_id=retailer.id, limit=limit, offset=offset
    )
    return CampaignListResponse(items=await svc.serialize(items), total=total)


@retailer_router.post("/campaigns", response_model=CampaignItem, status_code=201)
async def retailer_create_campaign(
    payload: CampaignCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    user: Annotated[User, Depends(require_retailer)],
) -> CampaignItem:
    svc = CommunityBuyingService(db)
    return await _one(
        svc, await svc.create(req=payload, actor_user_id=user.id, retailer=retailer)
    )


@retailer_router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignItem)
async def retailer_cancel_campaign(
    campaign_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> CampaignItem:
    svc = CommunityBuyingService(db)
    return await _one(svc, await svc.cancel(campaign_id, retailer=retailer))


@admin_router.get("/campaigns", response_model=CampaignListResponse)
async def admin_campaigns(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Literal["OPEN", "SUCCESSFUL", "FAILED", "CANCELLED"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CampaignListResponse:
    svc = CommunityBuyingService(db)
    items, total = await svc.list(
        status=status, retailer_id=None, limit=limit, offset=offset
    )
    return CampaignListResponse(items=await svc.serialize(items), total=total)


@admin_router.post("/campaigns", response_model=CampaignItem, status_code=201)
async def admin_create_campaign(
    payload: CampaignCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> CampaignItem:
    svc = CommunityBuyingService(db)
    return await _one(
        svc, await svc.create(req=payload, actor_user_id=admin.id, retailer=None)
    )


@admin_router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignItem)
async def admin_cancel_campaign(
    campaign_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> CampaignItem:
    svc = CommunityBuyingService(db)
    return await _one(svc, await svc.cancel(campaign_id, retailer=None))
