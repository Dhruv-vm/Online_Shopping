import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.price_intel.schemas import PriceIntelligenceResponse
from app.modules.price_intel.service import PriceIntelligenceService

router = APIRouter(prefix="/price-intelligence", tags=["Price Intelligence"])


@router.get(
    "/listings/{listing_id}",
    response_model=PriceIntelligenceResponse,
    summary="Public: price history, lowest/highest/average and discount authenticity",
)
async def get_listing_price_intelligence(
    listing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=90)] = 90,
) -> PriceIntelligenceResponse:
    return await PriceIntelligenceService(db).get_listing_intelligence(listing_id, days)
