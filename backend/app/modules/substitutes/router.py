import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.substitutes.schemas import (
    SubstituteListResponse,
    SubstituteType,
)
from app.modules.substitutes.service import SubstituteService

router = APIRouter(prefix="/substitutes", tags=["Substitutes"])


@router.get(
    "/listings/{listing_id}",
    response_model=SubstituteListResponse,
    summary="Get intelligent substitutes for a product listing",
)
async def get_listing_substitutes(
    listing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    type: Annotated[
        SubstituteType | None,
        Query(description="Filter by substitute category"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=20, description="Maximum number of substitutes"),
    ] = 10,
    in_stock_only: Annotated[
        bool,
        Query(description="Only return verified in-stock substitutes"),
    ] = True,
) -> SubstituteListResponse:
    service = SubstituteService(db)
    return await service.get_substitutes_for_listing(
        listing_id=listing_id,
        filter_type=type,
        limit=limit,
        in_stock_only=in_stock_only,
    )
