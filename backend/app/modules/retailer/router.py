import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_retailer,
)
from app.modules.identity.schemas import MessageResponse
from app.modules.retailer.schemas import (
    CatalogueProductLookupItem,
    RetailerBulkInventoryAdjustmentRequest,
    RetailerInventoryAdjustmentRequest,
    RetailerInventoryDashboardResponse,
    RetailerInventoryItemResponse,
    RetailerListingCreateRequest,
    RetailerListingListResponse,
    RetailerListingResponse,
    RetailerListingUpdateRequest,
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


# ================= Store Profile & Overview =================


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


# ================= Platform Catalogue Lookup =================


@router.get(
    "/catalogue/products",
    response_model=list[CatalogueProductLookupItem],
    summary="Browse canonical platform products to add to store",
)
async def get_catalogue_products(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[
        str | None, Query(description="Search product name or brand")
    ] = None,
    category_id: Annotated[
        uuid.UUID | None, Query(description="Filter by category")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CatalogueProductLookupItem]:
    service = RetailerService(db)
    return await service.get_catalogue_products(
        retailer=retailer,
        search=search,
        category_id=category_id,
        limit=limit,
        offset=offset,
    )


# ================= Product Listings =================


@router.get(
    "/listings",
    response_model=RetailerListingListResponse,
    summary="List product listings belonging to the retailer",
)
async def list_retailer_listings(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[
        str | None, Query(description="Search name, SKU, or seller SKU")
    ] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status")
    ] = None,
    is_low_stock: Annotated[
        bool | None, Query(description="Filter low-stock items")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RetailerListingListResponse:
    service = RetailerService(db)
    return await service.list_listings(
        retailer=retailer,
        search=search,
        is_active=is_active,
        is_low_stock=is_low_stock,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/listings",
    response_model=RetailerListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new store product listing with initial inventory",
)
async def create_retailer_listing(
    body: RetailerListingCreateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingResponse:
    service = RetailerService(db)
    listing = await service.create_listing(retailer, body)
    await db.commit()
    return listing


@router.get(
    "/listings/{listing_id}",
    response_model=RetailerListingResponse,
    summary="Get single product listing details",
)
async def get_retailer_listing(
    listing_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingResponse:
    service = RetailerService(db)
    return await service.get_listing(listing_id, retailer)


@router.put(
    "/listings/{listing_id}",
    response_model=RetailerListingResponse,
    summary="Update listing pricing, SKU, and status",
)
async def update_retailer_listing(
    listing_id: uuid.UUID,
    body: RetailerListingUpdateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingResponse:
    service = RetailerService(db)
    updated = await service.update_listing(listing_id, retailer, body)
    await db.commit()
    return updated


@router.delete(
    "/listings/{listing_id}",
    response_model=MessageResponse,
    summary="Deactivate or delete a store listing",
)
async def delete_retailer_listing(
    listing_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = RetailerService(db)
    await service.delete_listing(listing_id, retailer)
    await db.commit()
    return MessageResponse(message="Listing successfully deactivated.")


# ================= Inventory Management =================


@router.get(
    "/inventory",
    response_model=RetailerInventoryDashboardResponse,
    summary="Get real-time stock levels and inventory alerts",
)
async def get_retailer_inventory(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[
        str | None, Query(description="Search product name or SKU")
    ] = None,
    status_filter: Annotated[
        str | None,
        Query(description="Filter: ALL, LOW_STOCK, OUT_OF_STOCK, IN_STOCK"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RetailerInventoryDashboardResponse:
    service = RetailerService(db)
    return await service.get_inventory_dashboard(
        retailer=retailer,
        search=search,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/listings/{listing_id}/inventory",
    response_model=RetailerInventoryItemResponse,
    summary="Adjust stock levels or update low-stock alert threshold",
)
async def adjust_retailer_inventory(
    listing_id: uuid.UUID,
    body: RetailerInventoryAdjustmentRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerInventoryItemResponse:
    service = RetailerService(db)
    adjusted = await service.adjust_inventory(listing_id, retailer, body)
    await db.commit()
    return adjusted


@router.post(
    "/inventory/bulk-adjust",
    response_model=list[RetailerInventoryItemResponse],
    summary="Bulk update stock levels across multiple listings",
)
async def bulk_adjust_inventory(
    body: RetailerBulkInventoryAdjustmentRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RetailerInventoryItemResponse]:
    service = RetailerService(db)
    results = await service.bulk_adjust_inventory(retailer, body)
    await db.commit()
    return results
