import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.admin.schemas import (
    AdminOverviewResponse,
    AdminRetailerListItem,
    RetailerVerifyRequest,
)
from app.modules.admin.service import AdminService
from app.modules.identity.dependencies import require_admin

router = APIRouter(
    prefix="/admin",
    tags=["Admin Portal"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Get platform overview KPIs and counts",
)
async def get_admin_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOverviewResponse:
    service = AdminService(db)
    return await service.get_overview()


@router.get(
    "/retailers",
    response_model=list[AdminRetailerListItem],
    summary="List retailers with verification status and ownership details",
)
async def list_admin_retailers(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(
        None, description="Filter by status: PENDING, VERIFIED, SUSPENDED"
    ),
) -> list[AdminRetailerListItem]:
    service = AdminService(db)
    return await service.list_retailers(status=status)


@router.post(
    "/retailers/{retailer_id}/verify",
    response_model=AdminRetailerListItem,
    summary="Update retailer verification status (VERIFIED, REJECTED, SUSPENDED)",
)
async def verify_retailer(
    retailer_id: uuid.UUID,
    body: RetailerVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminRetailerListItem:
    service = AdminService(db)
    result = await service.verify_retailer(retailer_id, body)
    await db.commit()
    return result
