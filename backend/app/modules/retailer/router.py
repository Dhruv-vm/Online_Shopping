import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_retailer,
    verify_csrf_token,
)
from app.modules.identity.schemas import MessageResponse
from app.modules.retailer.schemas import (
    CatalogueProductLookupItem,
    RetailerAnalyticsResponse,
    RetailerBulkInventoryAdjustmentRequest,
    RetailerInventoryAdjustmentRequest,
    RetailerInventoryDashboardResponse,
    RetailerInventoryItemResponse,
    RetailerListingCreateRequest,
    RetailerListingListResponse,
    RetailerListingResponse,
    RetailerListingUpdateRequest,
    RetailerOfferCreateRequest,
    RetailerOfferItem,
    RetailerOfferUpdateRequest,
    RetailerOrderDetailResponse,
    RetailerOrderListResponse,
    RetailerOrderStatusUpdateRequest,
    RetailerOverviewResponse,
    RetailerProductCreateRequest,
    RetailerProfileResponse,
    RetailerProfileUpdateRequest,
)
from app.modules.retailer.service import RetailerService

router = APIRouter(
    prefix="/retailer",
    tags=["Retailer Portal"],
    dependencies=[Depends(require_retailer), Depends(verify_csrf_token)],
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
@router.patch(
    "/listings/{listing_id}",
    response_model=RetailerListingResponse,
    summary="Update listing pricing, SKU, and status (patch)",
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


# ================= Custom Product Creation =================


@router.post(
    "/products",
    response_model=RetailerListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom product, variant, listing and initial inventory in one step",
)
async def create_custom_retailer_product(
    body: RetailerProductCreateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingResponse:
    service = RetailerService(db)
    listing = await service.create_custom_product_and_listing(retailer, body)
    await db.commit()
    return listing


# ================= Retailer Orders Management =================


@router.get(
    "/orders",
    response_model=RetailerOrderListResponse,
    summary="List orders containing store items with tenant isolation",
)
async def list_retailer_orders(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[str | None, Query(description="Filter by order status")] = None,
    search: Annotated[str | None, Query(description="Search order number")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RetailerOrderListResponse:
    service = RetailerService(db)
    return await service.list_orders(
        retailer=retailer,
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/orders/{order_id}",
    response_model=RetailerOrderDetailResponse,
    summary="Get single order detail scoped to this retailer",
)
async def get_retailer_order_detail(
    order_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerOrderDetailResponse:
    service = RetailerService(db)
    return await service.get_order_detail(order_id, retailer)


@router.patch(
    "/orders/{order_id}/status",
    response_model=RetailerOrderDetailResponse,
    summary="Update fulfillment status of an order",
)
async def update_retailer_order_status(
    order_id: uuid.UUID,
    body: RetailerOrderStatusUpdateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerOrderDetailResponse:
    service = RetailerService(db)
    updated = await service.update_order_status(order_id, retailer, body)
    await db.commit()
    return updated


# ================= Retailer Offers & Discounts =================


@router.get(
    "/offers",
    response_model=list[RetailerOfferItem],
    summary="List promotional offers and discounts created by retailer",
)
async def list_retailer_offers(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RetailerOfferItem]:
    service = RetailerService(db)
    return await service.list_offers(retailer)


@router.post(
    "/offers",
    response_model=RetailerOfferItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new store offer or discount",
)
async def create_retailer_offer(
    body: RetailerOfferCreateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerOfferItem:
    service = RetailerService(db)
    offer = await service.create_offer(retailer, body)
    await db.commit()
    return offer


@router.put(
    "/offers/{offer_id}",
    response_model=RetailerOfferItem,
    summary="Update an existing store offer",
)
async def update_retailer_offer(
    offer_id: uuid.UUID,
    body: RetailerOfferUpdateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerOfferItem:
    service = RetailerService(db)
    offer = await service.update_offer(offer_id, retailer, body)
    await db.commit()
    return offer


@router.delete(
    "/offers/{offer_id}",
    response_model=MessageResponse,
    summary="Deactivate a store offer",
)
async def delete_retailer_offer(
    offer_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    service = RetailerService(db)
    await service.delete_offer(offer_id, retailer)
    await db.commit()
    return MessageResponse(message="Offer successfully deactivated.")


# ================= Retailer Sales Analytics =================


@router.get(
    "/analytics",
    response_model=RetailerAnalyticsResponse,
    summary="Get comprehensive store sales analytics and metrics",
)
async def get_retailer_analytics(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerAnalyticsResponse:
    service = RetailerService(db)
    return await service.get_analytics(retailer)


# ================= Onboarding & media =================
from app.modules.retailer import service as _svc_mod  # noqa: E402
from app.modules.retailer.schemas import (  # noqa: E402
    ImageUploadRequest,
    RetailerDocumentCreateRequest,
    RetailerDocumentItem,
)


def _doc_item(d) -> RetailerDocumentItem:
    return RetailerDocumentItem(
        id=d.id,
        document_type=d.document_type,
        document_number=d.document_number,
        has_file=bool(d.document_url),
        status=d.status,
        rejection_reason=d.rejection_reason,
        created_at=d.created_at,
    )


@router.get("/documents", response_model=list[RetailerDocumentItem])
async def list_verification_documents(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[RetailerDocumentItem]:
    return [_doc_item(d) for d in await _svc_mod.list_documents(db, retailer)]


@router.post("/documents", response_model=RetailerDocumentItem, status_code=201)
async def submit_verification_document(
    body: RetailerDocumentCreateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerDocumentItem:
    """Upload a GSTIN certificate, PAN, licence or address proof for review.
    Files are stored privately and are visible only to BASKET admins."""
    doc = await _svc_mod.submit_document(db, retailer, body)
    await db.commit()
    await db.refresh(doc)
    return _doc_item(doc)


@router.post("/verification/resubmit", response_model=RetailerProfileResponse)
async def resubmit_verification(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerProfileResponse:
    r = await _svc_mod.resubmit_for_verification(db, retailer)
    await db.commit()
    await db.refresh(r)
    return RetailerProfileResponse.model_validate(r)


@router.put("/listings/{listing_id}/image")
async def upload_listing_image(
    listing_id: uuid.UUID,
    body: ImageUploadRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    url = await _svc_mod.set_listing_image(db, retailer, listing_id, body)
    await db.commit()
    return {"listing_id": str(listing_id), "image_url": url}


@router.delete("/listings/{listing_id}/image")
async def remove_listing_image(
    listing_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await _svc_mod.set_listing_image(db, retailer, listing_id, None)
    await db.commit()
    return {"listing_id": str(listing_id), "image_url": None}
