from __future__ import annotations

import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.search.schemas import SearchResponseSchema, SuggestionsResponse
from app.modules.search.service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])
logger = logging.getLogger(__name__)

_search_service = SearchService()


def get_search_service() -> SearchService:
    return _search_service


@router.get("", response_model=SearchResponseSchema)
async def search_products(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[SearchService, Depends(get_search_service)],
    q: Annotated[str | None, Query(description="Free-text search query")] = None,
    category: Annotated[str | None, Query(description="Category slug filter")] = None,
    brand: Annotated[str | None, Query(description="Brand name filter")] = None,
    retailer_id: Annotated[
        uuid.UUID | None,
        Query(description="Filter products offered by specific retailer"),
    ] = None,
    min_price: Annotated[
        int | None, Query(ge=0, description="Minimum price in paise")
    ] = None,
    max_price: Annotated[
        int | None, Query(ge=0, description="Maximum price in paise")
    ] = None,
    in_stock: Annotated[
        bool, Query(description="Filter only items currently in stock")
    ] = False,
    sort: Annotated[
        Literal["relevance", "price_asc", "price_desc", "rating_desc", "newest"],
        Query(description="Sorting criteria"),
    ] = "relevance",
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    page_size: Annotated[int, Query(ge=1, le=50, description="Items per page")] = 20,
    force_fallback: Annotated[
        bool, Query(description="Force PostgreSQL fallback for testing")
    ] = False,
) -> SearchResponseSchema:
    """
    Universal multi-category, multi-retailer product search API.
    Guaranteed high availability via circuit breaker with transparent SQL fallback.
    """
    from app.core.config import settings

    result = await service.search(
        db_session=db,
        q=q,
        category_slug=category,
        brand=brand,
        retailer_id=retailer_id,
        min_price_paise=min_price,
        max_price_paise=max_price,
        in_stock_only=in_stock,
        sort=sort,
        page=page,
        page_size=page_size,
        # Diagnostic switch only; in production it would let any caller bypass
        # OpenSearch and push load onto PostgreSQL.
        force_fallback=force_fallback and not settings.is_production,
    )
    if result.total == 0 and q and len(q.strip()) >= 2 and page == 1:
        await _record_zero_search(request, db, q.strip(), category)
    return result


async def _record_zero_search(
    request: Request, db: AsyncSession, q: str, category_slug: str | None
) -> None:
    """Phase 3A: a search with no results is an unmet-demand signal."""
    try:
        from app.modules.cart.dependencies import get_current_user_optional
        from app.modules.demand.service import DemandService, caller_identity

        user = await get_current_user_optional(request, db)
        uid, guest = caller_identity(request, user)
        async with db.begin_nested():
            await DemandService(db).record_signal(
                signal_type="ZERO_SEARCH",
                query_text=q[:200],
                user_id=uid,
                guest_token_hash=guest,
            )
    except Exception as exc:  # demand capture must never break search
        logger.warning("Zero-result demand capture skipped: %s", exc)


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_search_suggestions(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[SearchService, Depends(get_search_service)],
    q: Annotated[str, Query(min_length=1, description="Partial search query")] = ...,
    limit: Annotated[
        int, Query(ge=1, le=10, description="Max suggestions to return")
    ] = 5,
) -> SuggestionsResponse:
    """Type-ahead auto-completion suggestions for product search bar."""
    return await service.get_suggestions(
        db_session=db,
        query=q,
        limit=limit,
    )
