from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.modules.catalogue.models import Retailer
from app.modules.identity.dependencies import (
    get_current_retailer,
    require_admin,
    require_retailer,
)
from app.modules.identity.models import User
from app.modules.passport.schemas import (
    AdminClaimQueueResponse,
    AdminClaimRejectRequest,
    AdminClaimResponse,
    AdminProductPassportUpsertRequest,
    ClaimReviewHistoryItem,
    PublicListingPassportResponse,
    PublicProductPassportResponse,
    RetailerClaimCreateRequest,
    RetailerClaimResponse,
    RetailerClaimUpdateRequest,
    RetailerListingPassportDetailResponse,
    RetailerListingPassportUpsertRequest,
)
from app.modules.passport.service import PassportService

# ================= Public Customer Endpoints =================

public_router = APIRouter(tags=["Product Passport"])


@public_router.get(
    "/products/{id}/passport",
    response_model=PublicProductPassportResponse,
    summary="Get verified product passport and selected listing facts",
)
@public_router.get(
    "/passport/products/{id}",
    response_model=PublicProductPassportResponse,
    include_in_schema=False,
)
async def get_public_product_passport(
    id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    listing_id: Annotated[
        uuid.UUID | None,
        Query(description="Selected listing UUID to include seller-specific facts"),
    ] = None,
) -> PublicProductPassportResponse:
    service = PassportService(db)
    return await service.get_public_passport(id, listing_id=listing_id)


@public_router.get(
    "/passport/listings/{listing_id}",
    response_model=PublicListingPassportResponse,
    summary="Get public listing passport for a specific retailer listing",
)
async def get_public_listing_passport(
    listing_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublicListingPassportResponse:
    service = PassportService(db)
    listing = await service.repo.get_listing_by_id(listing_id)
    if not listing:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing {listing_id} not found",
        )
    resp = await service._resolve_public_listing_passport(
        listing_id, listing.variant.product_id
    )
    if not resp:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing passport not found",
        )
    return resp


# ================= Retailer Portal Endpoints =================

retailer_router = APIRouter(
    prefix="/retailer/passport",
    tags=["Retailer Passport Portal"],
    dependencies=[Depends(require_retailer)],
)


@retailer_router.get(
    "/listings/{listing_id}",
    response_model=RetailerListingPassportDetailResponse,
    summary="Get listing passport and claims submitted by the current retailer",
)
async def get_retailer_listing_passport(
    listing_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingPassportDetailResponse:
    service = PassportService(db)
    return await service.get_retailer_listing_passport(listing_id, retailer.id)


@retailer_router.put(
    "/listings/{listing_id}",
    response_model=RetailerListingPassportDetailResponse,
    summary="Upsert condition, seller warranty, and packaging notes for own listing",
)
async def upsert_retailer_listing_passport(
    listing_id: uuid.UUID,
    body: RetailerListingPassportUpsertRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerListingPassportDetailResponse:
    service = PassportService(db)
    return await service.upsert_retailer_listing_passport(
        listing_id=listing_id, retailer_id=retailer.id, req=body
    )


@retailer_router.post(
    "/listings/{listing_id}/claims",
    response_model=RetailerClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new claim and evidence reference for moderation review",
)
async def submit_retailer_claim(
    listing_id: uuid.UUID,
    body: RetailerClaimCreateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    current_user: Annotated[User, Depends(require_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerClaimResponse:
    service = PassportService(db)
    return await service.create_retailer_claim(
        listing_id=listing_id,
        retailer_id=retailer.id,
        user_id=current_user.id,
        req=body,
    )


@retailer_router.put(
    "/claims/{claim_id}",
    response_model=RetailerClaimResponse,
    summary="Update an existing claim (re-triggers PENDING review status)",
)
async def update_retailer_claim(
    claim_id: uuid.UUID,
    body: RetailerClaimUpdateRequest,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetailerClaimResponse:
    service = PassportService(db)
    return await service.update_retailer_claim(
        claim_id=claim_id,
        retailer_id=retailer.id,
        req=body,
    )


@retailer_router.get(
    "/claims",
    response_model=list[RetailerClaimResponse],
    summary="List all claims submitted by the current retailer with review statuses",
)
async def list_retailer_claims(
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
    listing_id: Annotated[
        uuid.UUID | None,
        Query(description="Filter claims by listing UUID"),
    ] = None,
) -> list[RetailerClaimResponse]:
    service = PassportService(db)
    return await service.list_retailer_claims(retailer.id, listing_id=listing_id)


@retailer_router.get(
    "/claims/{claim_id}/history",
    response_model=list[ClaimReviewHistoryItem],
    summary="Get complete audit review and revision history for a claim",
)
async def get_retailer_claim_history(
    claim_id: uuid.UUID,
    retailer: Annotated[Retailer, Depends(get_current_retailer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ClaimReviewHistoryItem]:
    service = PassportService(db)
    return await service.get_retailer_claim_history(claim_id, retailer.id)


# ================= Admin Portal Endpoints =================

admin_router = APIRouter(
    prefix="/admin/passport",
    tags=["Admin Passport Portal"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get(
    "/queue",
    response_model=AdminClaimQueueResponse,
    summary="Get paginated pending claims moderation queue",
)
async def get_admin_claims_queue(
    db: Annotated[AsyncSession, Depends(get_db)],
    status: Annotated[
        str | None,
        Query(description="Filter by review status: PENDING, VERIFIED, REJECTED, ALL"),
    ] = None,
    scope: Annotated[
        str | None,
        Query(description="Filter by claim scope: PRODUCT, LISTING, ALL"),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="Search in key, value, retailer name or product name"),
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> AdminClaimQueueResponse:
    service = PassportService(db)
    return await service.get_admin_claim_queue(
        status=status,
        scope=scope,
        search=search,
        page=page,
        limit=limit,
    )


@admin_router.post(
    "/claims/{claim_id}/verify",
    response_model=AdminClaimResponse,
    summary="Verify and approve a submitted claim",
)
async def verify_claim(
    claim_id: uuid.UUID,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminClaimResponse:
    service = PassportService(db)
    return await service.verify_claim(claim_id, current_admin.id)


@admin_router.post(
    "/claims/{claim_id}/reject",
    response_model=AdminClaimResponse,
    summary="Reject a claim with a mandatory rejection reason",
)
async def reject_claim(
    claim_id: uuid.UUID,
    body: AdminClaimRejectRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminClaimResponse:
    service = PassportService(db)
    return await service.reject_claim(
        claim_id=claim_id,
        admin_id=current_admin.id,
        rejection_reason=body.rejection_reason,
    )


@admin_router.get(
    "/claims/{claim_id}/history",
    response_model=list[ClaimReviewHistoryItem],
    summary="Get complete audit review and revision history for any claim",
)
async def get_admin_claim_history(
    claim_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ClaimReviewHistoryItem]:
    service = PassportService(db)
    return await service.get_admin_claim_history(claim_id)


@admin_router.put(
    "/products/{product_id}",
    response_model=PublicProductPassportResponse,
    summary="Authorized admin editing of canonical product passport specifications",
)
async def upsert_canonical_passport(
    product_id: uuid.UUID,
    body: AdminProductPassportUpsertRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublicProductPassportResponse:
    service = PassportService(db)
    return await service.upsert_canonical_passport(product_id, body)
