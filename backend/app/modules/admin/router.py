import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.admin.schemas import (
    AdminCatalogueProductCreateRequest,
    AdminCatalogueProductDetailResponse,
    AdminCatalogueProductListItem,
    AdminCatalogueProductUpdateRequest,
    AdminCatalogueVariantCreateRequest,
    AdminCatalogueVariantItem,
    AdminCatalogueVariantUpdateRequest,
    AdminCategoryCreateRequest,
    AdminCategoryListItem,
    AdminDealCreateRequest,
    AdminDealDetailResponse,
    AdminDealListItem,
    AdminDealUpdateRequest,
    AdminOverviewResponse,
    AdminRetailerDetailResponse,
    AdminRetailerListItem,
    AdminRetailerSalesAnalyticsResponse,
    DocumentVerifyRequest,
    RetailerDocumentItem,
    RetailerVerifyRequest,
)
from app.modules.admin.service import AdminService
from app.modules.identity.dependencies import require_admin, verify_csrf_token
from app.modules.identity.models import User

router = APIRouter(
    prefix="/admin",
    tags=["Admin Portal"],
    dependencies=[Depends(require_admin), Depends(verify_csrf_token)],
)


# ================= Overview =================


@router.get(
    "/overview",
    response_model=AdminOverviewResponse,
    summary="Get platform overview KPIs and counts",
)
async def get_admin_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOverviewResponse:
    service = AdminService(db)
    return await service.get_overview()


# ================= Retailer Verification & Approval =================


@router.get(
    "/retailers",
    response_model=list[AdminRetailerListItem],
    summary="List retailers with verification status and ownership details",
)
async def list_admin_retailers(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None,
        Query(
            description="Filter by status: ALL, PENDING, VERIFIED, REJECTED, SUSPENDED"
        ),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Search by store name, slug, email, or owner name"),
    ] = None,
    state: Annotated[
        str | None,
        Query(description="Filter by state code (e.g. KA, MH, DL)"),
    ] = None,
    is_active: Annotated[
        bool | None,
        Query(description="Filter by active status"),
    ] = None,
    include_test_fixtures: Annotated[
        bool,
        Query(description="Include quarantined automated-test stores"),
    ] = False,
) -> list[AdminRetailerListItem]:
    service = AdminService(db)
    return await service.list_retailers(
        status=status,
        search=search,
        state=state,
        is_active=is_active,
        include_test_fixtures=include_test_fixtures,
    )


@router.get(
    "/retailers/{retailer_id}",
    response_model=AdminRetailerDetailResponse,
    summary="Get detailed retailer profile, submitted documents, and verification audit trail",
)
async def get_admin_retailer(
    retailer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminRetailerDetailResponse:
    service = AdminService(db)
    return await service.get_retailer(retailer_id)


@router.get(
    "/retailers/{retailer_id}/analytics",
    response_model=AdminRetailerSalesAnalyticsResponse,
    summary="Get comprehensive store-level sales analytics and product-level sales breakdown",
)
async def get_admin_retailer_analytics(
    retailer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminRetailerSalesAnalyticsResponse:
    service = AdminService(db)
    return await service.get_retailer_sales_analytics(retailer_id)


@router.post(
    "/retailers/{retailer_id}/verify",
    response_model=AdminRetailerListItem,
    summary="Approve, reject, or suspend a retailer account with reviewer audit",
)
async def verify_retailer(
    retailer_id: uuid.UUID,
    body: RetailerVerifyRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminRetailerListItem:
    service = AdminService(db)
    result = await service.verify_retailer(retailer_id, body, admin=admin)
    await db.commit()
    return result


@router.post(
    "/retailers/{retailer_id}/documents/{document_id}/verify",
    response_model=RetailerDocumentItem,
    summary="Verify or reject a specific retailer compliance document",
)
async def verify_retailer_document(
    retailer_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerDocumentItem:
    service = AdminService(db)
    result = await service.verify_document(retailer_id, document_id, body)
    await db.commit()
    return result


# ================= Admin Catalogue Management =================


@router.get(
    "/catalogue/products",
    response_model=list[AdminCatalogueProductListItem],
    summary="List canonical platform catalogue products with variant & listing counts",
)
async def list_admin_catalogue_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    search: Annotated[
        str | None, Query(description="Search by name, brand, or slug")
    ] = None,
    category_id: Annotated[
        uuid.UUID | None, Query(description="Filter by category ID")
    ] = None,
    brand: Annotated[str | None, Query(description="Filter by brand")] = None,
    is_active: Annotated[
        bool | None, Query(description="Filter by active status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminCatalogueProductListItem]:
    service = AdminService(db)
    return await service.list_catalogue_products(
        search=search,
        category_id=category_id,
        brand=brand,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/catalogue/products",
    response_model=AdminCatalogueProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new canonical product and initial variants in the platform catalogue",
)
async def create_admin_catalogue_product(
    body: AdminCatalogueProductCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogueProductDetailResponse:
    service = AdminService(db)
    result = await service.create_catalogue_product(body)
    await db.commit()
    return result


@router.get(
    "/catalogue/products/{product_id}",
    response_model=AdminCatalogueProductDetailResponse,
    summary="Get canonical product details with variants, images, and retailer listing counts",
)
async def get_admin_catalogue_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogueProductDetailResponse:
    service = AdminService(db)
    return await service.get_catalogue_product(product_id)


@router.put(
    "/catalogue/products/{product_id}",
    response_model=AdminCatalogueProductDetailResponse,
    summary="Update canonical product details (never alters retailer pricing)",
)
async def update_admin_catalogue_product(
    product_id: uuid.UUID,
    body: AdminCatalogueProductUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogueProductDetailResponse:
    service = AdminService(db)
    result = await service.update_catalogue_product(product_id, body)
    await db.commit()
    return result


@router.delete(
    "/catalogue/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a canonical product",
)
async def delete_admin_catalogue_product(
    product_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = AdminService(db)
    await service.delete_catalogue_product(product_id)
    await db.commit()


@router.post(
    "/catalogue/products/{product_id}/variants",
    response_model=AdminCatalogueVariantItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add a canonical variant with unique SKU to an existing product",
)
async def create_admin_catalogue_variant(
    product_id: uuid.UUID,
    body: AdminCatalogueVariantCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogueVariantItem:
    service = AdminService(db)
    result = await service.create_variant(product_id, body)
    await db.commit()
    return result


@router.put(
    "/catalogue/variants/{variant_id}",
    response_model=AdminCatalogueVariantItem,
    summary="Update a canonical variant name, SKU, or attributes",
)
async def update_admin_catalogue_variant(
    variant_id: uuid.UUID,
    body: AdminCatalogueVariantUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCatalogueVariantItem:
    service = AdminService(db)
    result = await service.update_variant(variant_id, body)
    await db.commit()
    return result


@router.delete(
    "/catalogue/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a canonical variant",
)
async def delete_admin_catalogue_variant(
    variant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = AdminService(db)
    await service.delete_variant(variant_id)
    await db.commit()


@router.get(
    "/catalogue/categories",
    response_model=list[AdminCategoryListItem],
    summary="List category hierarchy with product counts",
)
async def list_admin_catalogue_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminCategoryListItem]:
    service = AdminService(db)
    return await service.list_categories()


@router.post(
    "/catalogue/categories",
    response_model=AdminCategoryListItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new canonical product category",
)
async def create_admin_catalogue_category(
    body: AdminCategoryCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminCategoryListItem:
    service = AdminService(db)
    result = await service.create_category(body)
    await db.commit()
    return result


# ================= Platform Deals & Promotions =================


@router.get(
    "/deals",
    response_model=list[AdminDealListItem],
    summary="List platform deals and promotions with scope and status filtering",
)
async def list_admin_deals(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None,
        Query(
            description="Filter by deal status: ALL, ACTIVE, SCHEDULED, EXPIRED, PAUSED"
        ),
    ] = None,
    scope: Annotated[
        str | None,
        Query(
            description="Filter by scope: ALL, PLATFORM_WIDE, CATEGORY, PRODUCT, LISTING"
        ),
    ] = None,
    search: Annotated[
        str | None, Query(description="Search by deal name or coupon code")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AdminDealListItem]:
    service = AdminService(db)
    return await service.list_deals(
        status_filter=status,
        scope=scope,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/deals",
    response_model=AdminDealDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and schedule a new platform-wide, category, or product deal",
)
async def create_admin_deal(
    body: AdminDealCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDealDetailResponse:
    service = AdminService(db)
    result = await service.create_deal(body)
    await db.commit()
    return result


@router.get(
    "/deals/{deal_id}",
    response_model=AdminDealDetailResponse,
    summary="Get platform deal details and performance stats",
)
async def get_admin_deal(
    deal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDealDetailResponse:
    service = AdminService(db)
    return await service.get_deal(deal_id)


@router.put(
    "/deals/{deal_id}",
    response_model=AdminDealDetailResponse,
    summary="Update deal rules, schedule, limits, or active toggle",
)
async def update_admin_deal(
    deal_id: uuid.UUID,
    body: AdminDealUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDealDetailResponse:
    service = AdminService(db)
    result = await service.update_deal(deal_id, body)
    await db.commit()
    return result


@router.delete(
    "/deals/{deal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate or cancel a platform deal",
)
async def delete_admin_deal(
    deal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = AdminService(db)
    await service.delete_deal(deal_id)
    await db.commit()


# ================= Media: canonical images & private documents =================
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel as _BM  # noqa: E402
from pydantic import Field as _F  # noqa: E402

from app.core.exceptions import AppException  # noqa: E402


class AdminImageUploadRequest(_BM):
    content_base64: str = _F(..., min_length=8, max_length=7_200_000)
    content_type: str = _F(..., max_length=32)
    alt_text: str | None = _F(None, max_length=255)
    make_primary: bool = False


@router.post("/catalogue/products/{product_id}/images", status_code=201)
async def admin_upload_product_image(
    product_id: uuid.UUID,
    body: AdminImageUploadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Upload a canonical product image (validated, stored by the media service)."""
    from sqlalchemy import func as _func
    from sqlalchemy import select as _select
    from sqlalchemy import update as _update

    from app.modules.catalogue.models import Product, ProductImage
    from app.modules.media.storage import Base64Upload, save_upload

    product = await db.get(Product, product_id)
    if product is None:
        raise AppException(
            code="PRODUCT_NOT_FOUND", message="Product not found.", status_code=404
        )
    url = save_upload(
        Base64Upload(
            content_base64=body.content_base64, content_type=body.content_type
        ),
        folder="products",
    )
    count = (
        await db.execute(
            _select(_func.count()).where(ProductImage.product_id == product_id)
        )
    ).scalar() or 0
    primary = body.make_primary or count == 0
    if primary:
        await db.execute(
            _update(ProductImage)
            .where(ProductImage.product_id == product_id)
            .values(is_primary=False)
        )
    img = ProductImage(
        id=uuid.uuid4(),
        product_id=product_id,
        url=url,
        alt_text=(body.alt_text or product.name)[:255],
        is_primary=primary,
        sort_order=int(count),
    )
    db.add(img)
    await db.flush()
    await AdminService(db)._sync_product_search(product_id)
    await db.commit()
    return {"id": str(img.id), "url": url, "is_primary": primary}


@router.delete("/catalogue/images/{image_id}")
async def admin_delete_product_image(
    image_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.modules.catalogue.models import ProductImage

    img = await db.get(ProductImage, image_id)
    if img is None:
        raise AppException(
            code="IMAGE_NOT_FOUND", message="Image not found.", status_code=404
        )
    pid = img.product_id
    await db.delete(img)
    await db.flush()
    await AdminService(db)._sync_product_search(pid)
    await db.commit()
    return {"deleted": str(image_id)}


@router.get("/retailers/{retailer_id}/documents/{document_id}/file")
async def admin_download_document(
    retailer_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Admins only: download a privately stored verification document."""
    from app.modules.catalogue.models import RetailerVerificationDocument
    from app.modules.media.storage import private_path

    doc = await db.get(RetailerVerificationDocument, document_id)
    if doc is None or doc.retailer_id != retailer_id:
        raise AppException(
            code="DOCUMENT_NOT_FOUND", message="Document not found.", status_code=404
        )
    path = private_path(doc.document_url or "")
    if path is None:
        raise AppException(
            code="DOCUMENT_FILE_UNAVAILABLE",
            message="No stored file for this document (number-only submission or external link).",
            status_code=404,
        )
    return FileResponse(path, filename=f"{doc.document_type.lower()}{path.suffix}")
