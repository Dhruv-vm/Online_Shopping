from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.search.schemas import SearchResponseSchema, SuggestionsResponse
from app.modules.search.service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])

_search_service = SearchService()


def get_search_service() -> SearchService:
    return _search_service


@router.get("", response_model=SearchResponseSchema)
async def search_products(
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
    return await service.search(
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
        force_fallback=force_fallback,
    )


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
