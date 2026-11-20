from __future__ import annotations

import math
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.passport.models import PassportClaim
from app.modules.passport.repository import PassportRepository
from app.modules.passport.schemas import (
    AdminClaimQueueResponse,
    AdminClaimResponse,
    AdminProductPassportUpsertRequest,
    ClaimReviewHistoryItem,
    ListingBrief,
    PublicClaimResponse,
    PublicListingPassportResponse,
    PublicProductPassportResponse,
    RetailerClaimCreateRequest,
    RetailerClaimResponse,
    RetailerClaimUpdateRequest,
    RetailerListingPassportDetailResponse,
    RetailerListingPassportUpsertRequest,
)


class PassportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PassportRepository(session)

    # ================= Public Customer Flow =================

    async def get_public_passport(
        self,
        identifier: str,
        listing_id: uuid.UUID | None = None,
    ) -> PublicProductPassportResponse:
        """Retrieve transparent, verified product passport for customers.

        Private evidence URLs, reviewer IDs, and rejection notes are never exposed.
        """
        product = await self.repo.get_product_by_id_or_slug(identifier)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product '{identifier}' not found",
            )

        # Build available listings brief for customer comparison
        # Follow strict catalogue marketplace visibility rules (is_active and verified active retailer)
        available_listings: list[ListingBrief] = []
        for variant in product.variants:
            for lst in variant.listings:
                retailer = getattr(lst, "retailer", None)
                if (
                    not lst.is_active
                    or not retailer
                    or not retailer.is_active
                    or getattr(retailer, "verification_status", "VERIFIED")
                    != "VERIFIED"
                ):
                    continue
                inv_available = lst.inventory.available_quantity if lst.inventory else 0
                available_listings.append(
                    ListingBrief(
                        listing_id=lst.id,
                        retailer_id=lst.retailer_id,
                        retailer_name=retailer.name,
                        selling_price_paise=lst.selling_price_paise,
                        is_in_stock=inv_available > 0,
                        item_condition="NEW",
                    )
                )

        passport = await self.repo.get_product_passport(product.id)

        # If no canonical passport exists yet, return a safe empty baseline
        if not passport:
            listing_passport_resp = None
            if listing_id:
                listing_passport_resp = await self._resolve_public_listing_passport(
                    listing_id, product.id
                )

            return PublicProductPassportResponse(
                id=None,
                product_id=product.id,
                product_name=product.name,
                brand=product.brand,
                category_name=product.category.name
                if product.category
                else "Uncategorized",
                manufacturer=None,
                country_of_origin=None,
                model_number=None,
                gtin_ean_upc=None,
                materials=[],
                technical_specs={},
                package_contents=[],
                usage_instructions=None,
                safety_instructions=None,
                warranty_info=None,
                certifications=[],
                claims=[],
                listing_passport=listing_passport_resp,
                available_listings=available_listings,
                created_at=None,
                updated_at=None,
            )

        # Map claims (filter sensitive evidence URLs/notes)
        raw_claims = await self.repo.get_public_claims_for_product(passport.id)
        claims = [self._map_public_claim(c) for c in raw_claims]

        listing_passport_resp = None
        if listing_id:
            listing_passport_resp = await self._resolve_public_listing_passport(
                listing_id, product.id
            )

        return PublicProductPassportResponse(
            id=passport.id,
            product_id=product.id,
            product_name=product.name,
            brand=product.brand,
            category_name=product.category.name
            if product.category
            else "Uncategorized",
            manufacturer=passport.manufacturer,
            country_of_origin=passport.country_of_origin,
            model_number=passport.model_number,
            gtin_ean_upc=passport.gtin_ean_upc,
            materials=passport.materials or [],
            technical_specs=passport.technical_specs or {},
            package_contents=passport.package_contents or [],
            usage_instructions=passport.usage_instructions,
            safety_instructions=passport.safety_instructions,
            warranty_info=passport.warranty_info,
            certifications=passport.certifications or [],
            claims=claims,
            listing_passport=listing_passport_resp,
            available_listings=available_listings,
            created_at=passport.created_at,
            updated_at=passport.updated_at,
        )

    async def _resolve_public_listing_passport(
        self, listing_id: uuid.UUID, product_id: uuid.UUID
    ) -> PublicListingPassportResponse | None:
        """Resolve listing passport ensuring it belongs to the target product and meets visibility rules."""
        listing = await self.repo.get_listing_by_id(listing_id)
        if (
            not listing
            or not listing.variant
            or listing.variant.product_id != product_id
            or not listing.is_active
            or not listing.retailer
            or not listing.retailer.is_active
            or getattr(listing.retailer, "verification_status", "VERIFIED")
            != "VERIFIED"
        ):
            return None

        raw_claims = await self.repo.get_public_claims_for_listing(listing_id)
        claims = [self._map_public_claim(c) for c in raw_claims]

        lst_passport = await self.repo.get_listing_passport(listing_id)
        if not lst_passport:
            return PublicListingPassportResponse(
                id=uuid.uuid4(),
                listing_id=listing.id,
                retailer_id=listing.retailer_id,
                retailer_name=listing.retailer.name if listing.retailer else "Retailer",
                item_condition="NEW",
                seller_warranty=None,
                packaging_notes=None,
                fulfillment_notes=None,
                claims=claims,
                created_at=listing.created_at,
                updated_at=listing.updated_at,
            )

        return PublicListingPassportResponse(
            id=lst_passport.id,
            listing_id=listing.id,
            retailer_id=listing.retailer_id,
            retailer_name=lst_passport.retailer.name
            if lst_passport.retailer
            else "Retailer",
            item_condition=lst_passport.item_condition,
            seller_warranty=lst_passport.seller_warranty,
            packaging_notes=lst_passport.packaging_notes,
            fulfillment_notes=lst_passport.fulfillment_notes,
            claims=claims,
            created_at=lst_passport.created_at,
            updated_at=lst_passport.updated_at,
        )

    def _map_public_claim(self, claim: PassportClaim) -> PublicClaimResponse:
        """Map claim into public schema.

        Evidence URLs are ONLY shown when is_public_evidence is True AND review_status is VERIFIED.
        Never leaks reviewer ID, submitter ID, or internal rejection reason.
        """
        show_evidence = (
            claim.is_public_evidence
            and claim.review_status == "VERIFIED"
            and claim.evidence_url
        )
        return PublicClaimResponse(
            id=claim.id,
            claim_scope=claim.claim_scope,
            claim_type=claim.claim_type,
            claim_key=claim.claim_key,
            claim_value=claim.claim_value,
            review_status=claim.review_status,
            is_public_evidence=claim.is_public_evidence,
            evidence_url=claim.evidence_url if show_evidence else None,
            evidence_type=claim.evidence_type if show_evidence else None,
            created_at=claim.created_at,
            reviewed_at=claim.reviewed_at,
        )

    # ================= Retailer Portal Flow =================

    async def get_retailer_listing_passport(
        self, listing_id: uuid.UUID, retailer_id: uuid.UUID
    ) -> RetailerListingPassportDetailResponse:
        """Fetch listing passport and submitted claims for the retailer who owns the listing."""
        listing = await self.repo.get_listing_by_id(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found",
            )
        if listing.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: listing belongs to another retailer",
            )

        lst_passport = await self.repo.get_listing_passport(listing_id)
        claims = await self.repo.get_claims_by_retailer(
            retailer_id, listing_id=listing_id
        )
        claim_responses = [RetailerClaimResponse.model_validate(c) for c in claims]

        if not lst_passport:
            return RetailerListingPassportDetailResponse(
                id=uuid.uuid4(),
                listing_id=listing.id,
                retailer_id=retailer_id,
                item_condition="NEW",
                seller_warranty=None,
                packaging_notes=None,
                fulfillment_notes=None,
                claims=claim_responses,
                created_at=listing.created_at,
                updated_at=listing.updated_at,
            )

        return RetailerListingPassportDetailResponse(
            id=lst_passport.id,
            listing_id=listing.id,
            retailer_id=retailer_id,
            item_condition=lst_passport.item_condition,
            seller_warranty=lst_passport.seller_warranty,
            packaging_notes=lst_passport.packaging_notes,
            fulfillment_notes=lst_passport.fulfillment_notes,
            claims=claim_responses,
            created_at=lst_passport.created_at,
            updated_at=lst_passport.updated_at,
        )

    async def upsert_retailer_listing_passport(
        self,
        listing_id: uuid.UUID,
        retailer_id: uuid.UUID,
        req: RetailerListingPassportUpsertRequest,
    ) -> RetailerListingPassportDetailResponse:
        """Create or update listing passport for the authenticated retailer."""
        listing = await self.repo.get_listing_by_id(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found",
            )
        if listing.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: listing belongs to another retailer",
            )

        data = {
            "item_condition": req.item_condition.value,
            "seller_warranty": req.seller_warranty,
            "packaging_notes": req.packaging_notes,
            "fulfillment_notes": req.fulfillment_notes,
        }
        lst_passport = await self.repo.upsert_listing_passport(
            listing_id=listing_id, retailer_id=retailer_id, data=data
        )

        claims = await self.repo.get_claims_by_retailer(
            retailer_id, listing_id=listing_id
        )
        claim_responses = [RetailerClaimResponse.model_validate(c) for c in claims]

        return RetailerListingPassportDetailResponse(
            id=lst_passport.id,
            listing_id=listing.id,
            retailer_id=retailer_id,
            item_condition=lst_passport.item_condition,
            seller_warranty=lst_passport.seller_warranty,
            packaging_notes=lst_passport.packaging_notes,
            fulfillment_notes=lst_passport.fulfillment_notes,
            claims=claim_responses,
            created_at=lst_passport.created_at,
            updated_at=lst_passport.updated_at,
        )

    async def create_retailer_claim(
        self,
        listing_id: uuid.UUID,
        retailer_id: uuid.UUID,
        user_id: uuid.UUID,
        req: RetailerClaimCreateRequest,
    ) -> RetailerClaimResponse:
        """Submit a new claim. Always starts in PENDING status."""
        listing = await self.repo.get_listing_by_id(listing_id)
        if not listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listing {listing_id} not found",
            )
        if listing.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: listing belongs to another retailer",
            )

        passport_id = None
        if req.claim_scope.value == "PRODUCT":
            # Link to canonical product passport if exists
            product_id = listing.variant.product_id if listing.variant else None
            if product_id:
                p_passport = await self.repo.get_product_passport(product_id)
                if not p_passport:
                    # Auto-initialize an empty canonical product passport if needed
                    p_passport = await self.repo.upsert_product_passport(product_id, {})
                passport_id = p_passport.id

        claim_data = {
            "passport_id": passport_id,
            "listing_id": listing_id,
            "retailer_id": retailer_id,
            "claim_scope": req.claim_scope.value,
            "claim_type": req.claim_type.strip(),
            "claim_key": req.claim_key.strip(),
            "claim_value": req.claim_value.strip(),
            "evidence_url": req.evidence_url,
            "evidence_type": req.evidence_type.strip(),
            "evidence_notes": req.evidence_notes,
            "is_public_evidence": req.is_public_evidence,
            "review_status": "PENDING",  # Strict non-negotiable rule 1
            "submitted_by_user_id": user_id,
            "rejection_reason": None,
            "reviewed_by_user_id": None,
            "reviewed_at": None,
        }

        claim = await self.repo.create_claim(claim_data)
        return RetailerClaimResponse.model_validate(claim)

    async def update_retailer_claim(
        self,
        claim_id: uuid.UUID,
        retailer_id: uuid.UUID,
        req: RetailerClaimUpdateRequest,
    ) -> RetailerClaimResponse:
        """Update claim content.

        Non-negotiable rule 4: Editing any claim triggers re-review and sets status to PENDING.
        """
        claim = await self.repo.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found",
            )
        if claim.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: claim belongs to another retailer",
            )

        update_dict: dict[str, Any] = {}
        if req.claim_type is not None:
            update_dict["claim_type"] = req.claim_type.strip()
        if req.claim_key is not None:
            update_dict["claim_key"] = req.claim_key.strip()
        if req.claim_value is not None:
            update_dict["claim_value"] = req.claim_value.strip()
        if req.evidence_url is not None:
            update_dict["evidence_url"] = req.evidence_url
        if req.evidence_type is not None:
            update_dict["evidence_type"] = req.evidence_type.strip()
        if req.evidence_notes is not None:
            update_dict["evidence_notes"] = req.evidence_notes
        if req.is_public_evidence is not None:
            update_dict["is_public_evidence"] = req.is_public_evidence

        claim = await self.repo.update_claim(claim, update_dict, retrigger_review=True)
        return RetailerClaimResponse.model_validate(claim)

    async def list_retailer_claims(
        self, retailer_id: uuid.UUID, listing_id: uuid.UUID | None = None
    ) -> list[RetailerClaimResponse]:
        """Fetch all claims submitted by the authenticated retailer."""
        claims = await self.repo.get_claims_by_retailer(
            retailer_id, listing_id=listing_id
        )
        return [RetailerClaimResponse.model_validate(c) for c in claims]

    async def get_retailer_claim_history(
        self,
        claim_id: uuid.UUID,
        retailer_id: uuid.UUID,
    ) -> list[ClaimReviewHistoryItem]:
        """Fetch audit trail of review history for a retailer's claim."""
        claim = await self.repo.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found",
            )
        if claim.retailer_id != retailer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: claim belongs to another retailer",
            )
        history = await self.repo.get_claim_review_history(claim_id)
        return [ClaimReviewHistoryItem.model_validate(h) for h in history]

    # ================= Admin Portal Flow =================

    async def get_admin_claim_queue(
        self,
        status: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> AdminClaimQueueResponse:
        """Retrieve paginated claims moderation queue."""
        raw_items, total = await self.repo.get_admin_claims_queue(
            status=status,
            scope=scope,
            search=search,
            page=page,
            limit=limit,
        )

        items = []
        for row in raw_items:
            claim: PassportClaim = row["claim"]
            items.append(
                AdminClaimResponse(
                    id=claim.id,
                    passport_id=claim.passport_id,
                    listing_id=claim.listing_id,
                    retailer_id=claim.retailer_id,
                    retailer_name=row["retailer_name"],
                    product_id=row["product_id"],
                    product_name=row["product_name"],
                    claim_scope=claim.claim_scope,
                    claim_type=claim.claim_type,
                    claim_key=claim.claim_key,
                    claim_value=claim.claim_value,
                    evidence_url=claim.evidence_url,
                    evidence_type=claim.evidence_type,
                    evidence_notes=claim.evidence_notes,
                    is_public_evidence=claim.is_public_evidence,
                    review_status=claim.review_status,
                    rejection_reason=claim.rejection_reason,
                    submitted_by_user_id=claim.submitted_by_user_id,
                    reviewed_by_user_id=claim.reviewed_by_user_id,
                    reviewed_at=claim.reviewed_at,
                    created_at=claim.created_at,
                    updated_at=claim.updated_at,
                )
            )

        pages = math.ceil(total / limit) if total > 0 else 1
        return AdminClaimQueueResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
        )

    async def verify_claim(
        self, claim_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AdminClaimResponse:
        """Approve claim and mark as VERIFIED."""
        claim = await self.repo.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found",
            )

        claim = await self.repo.verify_claim(claim, admin_id)
        return AdminClaimResponse.model_validate(claim)

    async def reject_claim(
        self, claim_id: uuid.UUID, admin_id: uuid.UUID, rejection_reason: str
    ) -> AdminClaimResponse:
        """Reject claim with a mandatory reason."""
        if not rejection_reason or not rejection_reason.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Rejection reason is required",
            )

        claim = await self.repo.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found",
            )

        claim = await self.repo.reject_claim(claim, admin_id, rejection_reason.strip())
        return AdminClaimResponse.model_validate(claim)

    async def get_admin_claim_history(
        self,
        claim_id: uuid.UUID,
    ) -> list[ClaimReviewHistoryItem]:
        """Fetch audit trail of review history for any claim (admin only)."""
        claim = await self.repo.get_claim_by_id(claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim {claim_id} not found",
            )
        history = await self.repo.get_claim_review_history(claim_id)
        return [ClaimReviewHistoryItem.model_validate(h) for h in history]

    async def upsert_canonical_passport(
        self,
        product_id: uuid.UUID,
        req: AdminProductPassportUpsertRequest,
    ) -> PublicProductPassportResponse:
        """Authorized admin editing of canonical product passport specifications."""
        product = await self.repo.get_product_by_id_or_slug(str(product_id))
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} not found",
            )

        data = {
            "manufacturer": req.manufacturer,
            "country_of_origin": req.country_of_origin,
            "model_number": req.model_number,
            "gtin_ean_upc": req.gtin_ean_upc,
            "materials": req.materials,
            "technical_specs": req.technical_specs,
            "package_contents": req.package_contents,
            "usage_instructions": req.usage_instructions,
            "safety_instructions": req.safety_instructions,
            "warranty_info": req.warranty_info,
            "certifications": req.certifications,
        }

        await self.repo.upsert_product_passport(product_id, data)
        return await self.get_public_passport(str(product_id))
