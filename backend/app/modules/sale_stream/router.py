import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.sale_stream.schemas import SaleStreamResponse
from app.modules.sale_stream.service import SaleStreamService

router = APIRouter(prefix="/sale-stream", tags=["Sale Stream"])


@router.get(
    "/live",
    response_model=SaleStreamResponse,
    summary="Public: live feed of price drops, flash deals and hot sellers (poll)",
)
async def live_sale_stream(
    db: Annotated[AsyncSession, Depends(get_db)],
    event_type: Literal["PRICE_DROP", "FLASH_DEAL", "HOT_SELLER"] | None = None,
    category_slug: Annotated[str | None, Query(max_length=120)] = None,
    before: datetime.datetime | None = None,
    since: datetime.datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SaleStreamResponse:
    """`before` pages older items; `since` returns only items newer than a previous
    `server_time` (efficient polling). Expired events are never returned."""
    return await SaleStreamService(db).live_feed(
        event_type=event_type,
        category_slug=category_slug,
        before=before,
        since=since,
        limit=limit,
    )
