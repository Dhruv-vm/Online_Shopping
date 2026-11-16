import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.schemas import (
    CategorySchema,
    ProductDetailSchema,
    ProductListResponseSchema,
    RetailerSchema,
)
from app.modules.catalogue.service import CatalogueService

router = APIRouter()


@router.get(
    "/categories",
    response_model=list[CategorySchema],
    tags=["Catalogue"],
    summary="List all active product categories",
)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CategorySchema]:
    service = CatalogueService(db)
    return await service.get_categories()


@router.get(
    "/retailers",
    response_model=list[RetailerSchema],
    tags=["Catalogue"],
    summary="List all active retail partners",
)
async def list_retailers(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RetailerSchema]:
    service = CatalogueService(db)
    return await service.get_retailers()


@router.get(
    "/products",
    response_model=ProductListResponseSchema,
    tags=["Catalogue"],
    summary="Browse and filter product catalogue",
)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_slug: Annotated[
        str | None, Query(description="Filter by category slug")
    ] = None,
    category_id: Annotated[
        uuid.UUID | None, Query(description="Filter by category UUID")
    ] = None,
    retailer_id: Annotated[
        uuid.UUID | None, Query(description="Filter by retailer UUID")
    ] = None,
    brand: Annotated[str | None, Query(description="Filter by brand name")] = None,
    search: Annotated[
        str | None, Query(description="Search query across name, brand, description")
    ] = None,
    min_price: Annotated[
        int | None, Query(ge=0, description="Minimum price in paise")
    ] = None,
    max_price: Annotated[
        int | None, Query(ge=0, description="Maximum price in paise")
    ] = None,
    in_stock: Annotated[
        bool | None, Query(description="Filter by stock availability")
    ] = None,
    sort_by: Annotated[
        str, Query(pattern="^(newest|price_asc|price_desc|name_asc)$")
    ] = "newest",
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ProductListResponseSchema:
    service = CatalogueService(db)
    return await service.list_products(
        category_slug=category_slug,
        category_id=category_id,
        retailer_id=retailer_id,
        brand=brand,
        search=search,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort_by=sort_by,
        page=page,
        limit=limit,
    )


@router.get(
    "/products/{id}",
    response_model=ProductDetailSchema,
    tags=["Catalogue"],
    summary="Get detailed product information by ID or slug",
)
async def get_product(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductDetailSchema:
    service = CatalogueService(db)
    return await service.get_product_detail(id)
