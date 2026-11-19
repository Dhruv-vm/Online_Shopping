from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_retailer,
)
from app.modules.retailer.schemas import (
    RetailerOverviewResponse,
    RetailerProfileResponse,
    RetailerProfileUpdateRequest,
)
from app.modules.retailer.service import RetailerService

router = APIRouter(
    prefix="/retailer",
    tags=["Retailer Portal"],
    dependencies=[Depends(require_retailer)],
)


@router.get(
    "/profile",
    response_model=RetailerProfileResponse,
    summary="Get current retailer store profile",
)
async def get_retailer_profile(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> RetailerProfileResponse:
    return RetailerProfileResponse.model_validate(retailer)


@router.put(
    "/profile",
    response_model=RetailerProfileResponse,
    summary="Update current retailer store profile",
)
async def update_retailer_profile(
    body: RetailerProfileUpdateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerProfileResponse:
    service = RetailerService(db)
    updated = await service.update_profile(retailer, body)
    await db.commit()
    return updated


@router.get(
    "/overview",
    response_model=RetailerOverviewResponse,
    summary="Get retailer store overview and dashboard KPIs",
)
async def get_retailer_overview(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerOverviewResponse:
    service = RetailerService(db)
    return await service.get_overview(retailer)
