import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_admin,
    require_retailer,
    require_role,
    verify_csrf_token,
)
from app.modules.identity.models import User
from app.modules.price_intel import extras
from app.modules.price_intel.schemas import (
    PriceAlertCreateRequest,
    PriceAlertItem,
    PriceComparisonResponse,
    PriceDataQualityResponse,
    PriceIntelligenceResponse,
    RetailerPriceInsight,
)
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


# Phase 3F completion: comparison, alerts, retailer insights, admin quality.

require_customer = require_role("customer")


@router.get(
    "/variants/{variant_id}/compare",
    response_model=PriceComparisonResponse,
    summary="Public: compare live prices for one variant across verified stores",
)
async def compare_variant(
    variant_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> PriceComparisonResponse:
    return await extras.compare_variant_prices(db, variant_id)


@router.get("/alerts", response_model=list[PriceAlertItem])
async def my_price_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> list[PriceAlertItem]:
    return await extras.list_price_alerts(db, user.id)


@router.post(
    "/alerts",
    response_model=PriceAlertItem,
    status_code=201,
    dependencies=[Depends(verify_csrf_token)],
)
async def create_price_alert(
    payload: PriceAlertCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> PriceAlertItem:
    return await extras.create_price_alert(
        db, user.id, payload.variant_id, payload.target_price_paise
    )


@router.delete(
    "/alerts/{alert_id}",
    response_model=PriceAlertItem,
    dependencies=[Depends(verify_csrf_token)],
)
async def cancel_price_alert(
    alert_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_customer)],
) -> PriceAlertItem:
    return await extras.cancel_price_alert(db, user.id, alert_id)


retailer_router = APIRouter(
    prefix="/retailer/price-insights",
    tags=["Price Intelligence (Retailer)"],
    dependencies=[Depends(require_retailer)],
)


@retailer_router.get("", response_model=list[RetailerPriceInsight])
async def retailer_insights(
    db: Annotated[AsyncSession, Depends(get_db)],
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
) -> list[RetailerPriceInsight]:
    return await extras.retailer_price_insights(db, retailer)


admin_router = APIRouter(
    prefix="/admin/price-intelligence",
    tags=["Price Intelligence (Admin)"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get("/quality", response_model=PriceDataQualityResponse)
async def admin_price_quality(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PriceDataQualityResponse:
    return await extras.price_data_quality(db)
