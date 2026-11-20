from __future__ import annotations

import datetime
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalogue.models import (
    Product,
    ProductListing,
    ProductVariant,
    Retailer,
)
from app.modules.passport.models import (
    ListingPassport,
    PassportClaim,
    PassportClaimReviewHistory,
    ProductPassport,
)


class PassportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_product_by_id_or_slug(self, identifier: str) -> Product | None:
        """Resolve product by UUID or slug, eager-loading category and variants."""
        try:
            val_uuid = uuid.UUID(identifier)
            query = select(Product).where(Product.id == val_uuid)
        except ValueError:
            query = select(Product).where(Product.slug == identifier)

        query = query.options(
            selectinload(Product.category),
            selectinload(Product.variants)
            .selectinload(ProductVariant.listings)
            .selectinload(ProductListing.retailer),
            selectinload(Product.variants)
            .selectinload(ProductVariant.listings)
            .selectinload(ProductListing.inventory),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_product_passport(
        self, product_id: uuid.UUID
    ) -> ProductPassport | None:
        """Fetch canonical product passport by product ID."""
        query = (
            select(ProductPassport)
            .where(ProductPassport.product_id == product_id)
            .options(
                selectinload(ProductPassport.claims),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_product_passport(
        self, product_id: uuid.UUID, data: dict[str, Any]
    ) -> ProductPassport:
        """Create or update canonical product passport."""
        passport = await self.get_product_passport(product_id)
        if not passport:
            passport = ProductPassport(product_id=product_id, **data)
            self.session.add(passport)
        else:
            for k, v in data.items():
                setattr(passport, k, v)

        await self.session.flush()
        await self.session.refresh(passport)
        return passport

    async def get_listing_passport(
        self, listing_id: uuid.UUID
    ) -> ListingPassport | None:
        """Fetch listing passport by listing ID."""
        query = (
            select(ListingPassport)
            .where(ListingPassport.listing_id == listing_id)
            .options(
                selectinload(ListingPassport.retailer),
                selectinload(ListingPassport.claims),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_listing_passport(
        self, listing_id: uuid.UUID, retailer_id: uuid.UUID, data: dict[str, Any]
    ) -> ListingPassport:
        """Create or update retailer listing passport."""
        passport = await self.get_listing_passport(listing_id)
        if not passport:
            passport = ListingPassport(
                listing_id=listing_id, retailer_id=retailer_id, **data
            )
            self.session.add(passport)
        else:
            for k, v in data.items():
                setattr(passport, k, v)

        await self.session.flush()
        await self.session.refresh(passport)
        return passport

    async def get_listing_by_id(self, listing_id: uuid.UUID) -> ProductListing | None:
        """Fetch listing with retailer and variant info."""
        query = (
            select(ProductListing)
            .where(ProductListing.id == listing_id)
            .options(
                selectinload(ProductListing.retailer),
                selectinload(ProductListing.inventory),
                selectinload(ProductListing.variant).selectinload(
                    ProductVariant.product
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_claim_by_id(self, claim_id: uuid.UUID) -> PassportClaim | None:
        """Fetch claim by ID with relationships and review history."""
        query = (
            select(PassportClaim)
            .where(PassportClaim.id == claim_id)
            .options(
                selectinload(PassportClaim.passport),
                selectinload(PassportClaim.listing_passport),
                selectinload(PassportClaim.review_history),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_claim(self, data: dict[str, Any]) -> PassportClaim:
        """Create a new claim record with initial SUBMITTED review history."""
        claim = PassportClaim(**data)
        self.session.add(claim)
        await self.session.flush()

        history = PassportClaimReviewHistory(
            claim_id=claim.id,
            claim_scope=claim.claim_scope,
            claim_type=claim.claim_type,
            claim_key=claim.claim_key,
            claim_value=claim.claim_value,
            evidence_url=claim.evidence_url,
            evidence_type=claim.evidence_type,
            evidence_notes=claim.evidence_notes,
            is_public_evidence=claim.is_public_evidence,
            action="SUBMITTED",
            review_status="PENDING",
            reviewer_id=None,
            rejection_reason=None,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(claim)
        self.session.expire(claim, ["review_history"])
        return (await self.get_claim_by_id(claim.id)) or claim

    async def update_claim(
        self,
        claim: PassportClaim,
        data: dict[str, Any],
        retrigger_review: bool = True,
    ) -> PassportClaim:
        """Update claim content and set to PENDING while preserving previous moderation feedback."""
        for k, v in data.items():
            if v is not None:
                setattr(claim, k, v)

        if retrigger_review:
            claim.version = (claim.version or 1) + 1
            claim.review_status = "PENDING"
            # We preserve claim.rejection_reason so retailer can continue to see prior feedback.
            history = PassportClaimReviewHistory(
                claim_id=claim.id,
                claim_scope=claim.claim_scope,
                claim_type=claim.claim_type,
                claim_key=claim.claim_key,
                claim_value=claim.claim_value,
                evidence_url=claim.evidence_url,
                evidence_type=claim.evidence_type,
                evidence_notes=claim.evidence_notes,
                is_public_evidence=claim.is_public_evidence,
                action="REVISED",
                review_status="PENDING",
                reviewer_id=None,
                rejection_reason=None,
            )
            self.session.add(history)

        await self.session.flush()
        await self.session.refresh(claim)
        self.session.expire(claim, ["review_history"])
        return (await self.get_claim_by_id(claim.id)) or claim

    async def delete_claim(self, claim: PassportClaim) -> None:
        """Delete claim record."""
        await self.session.delete(claim)
        await self.session.flush()

    async def get_public_claims_for_product(
        self, passport_id: uuid.UUID
    ) -> list[PassportClaim]:
        """Fetch claims for a canonical product passport."""
        query = (
            select(PassportClaim)
            .where(
                PassportClaim.passport_id == passport_id,
                PassportClaim.claim_scope == "PRODUCT",
            )
            .order_by(PassportClaim.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_public_claims_for_listing(
        self, listing_id: uuid.UUID
    ) -> list[PassportClaim]:
        """Fetch claims for a listing."""
        query = (
            select(PassportClaim)
            .where(
                PassportClaim.listing_id == listing_id,
                PassportClaim.claim_scope == "LISTING",
            )
            .order_by(PassportClaim.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_claims_by_retailer(
        self, retailer_id: uuid.UUID, listing_id: uuid.UUID | None = None
    ) -> list[PassportClaim]:
        """Fetch all claims submitted by a specific retailer with review history."""
        query = (
            select(PassportClaim)
            .options(selectinload(PassportClaim.review_history))
            .where(PassportClaim.retailer_id == retailer_id)
        )
        if listing_id:
            query = query.where(PassportClaim.listing_id == listing_id)
        query = query.order_by(PassportClaim.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_admin_claims_queue(
        self,
        status: str | None = None,
        scope: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch paginated claims queue for admin review with retailer, product, and review history."""
        query = (
            select(
                PassportClaim,
                Retailer.name.label("retailer_name"),
                Product.id.label("prod_id"),
                Product.name.label("prod_name"),
            )
            .options(selectinload(PassportClaim.review_history))
            .outerjoin(Retailer, PassportClaim.retailer_id == Retailer.id)
            .outerjoin(ProductPassport, PassportClaim.passport_id == ProductPassport.id)
            .outerjoin(ProductListing, PassportClaim.listing_id == ProductListing.id)
            .outerjoin(ProductVariant, ProductListing.variant_id == ProductVariant.id)
            .outerjoin(
                Product,
                (ProductPassport.product_id == Product.id)
                | (ProductVariant.product_id == Product.id),
            )
        )

        if status and status.upper() != "ALL":
            query = query.where(PassportClaim.review_status == status.upper())
        if scope and scope.upper() != "ALL":
            query = query.where(PassportClaim.claim_scope == scope.upper())
        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                (PassportClaim.claim_key.ilike(search_pattern))
                | (PassportClaim.claim_value.ilike(search_pattern))
                | (Retailer.name.ilike(search_pattern))
                | (Product.name.ilike(search_pattern))
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_res = await self.session.execute(count_query)
        total = count_res.scalar_one()

        # Paginate
        offset = (page - 1) * limit
        query = (
            query.order_by(
                # Sort PENDING first, then newest
                PassportClaim.review_status == "PENDING",
                PassportClaim.created_at.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        rows = (await self.session.execute(query)).all()
        items = []
        for claim, retailer_name, prod_id, prod_name in rows:
            items.append(
                {
                    "claim": claim,
                    "retailer_name": retailer_name,
                    "product_id": prod_id,
                    "product_name": prod_name,
                }
            )

        return items, total

    async def get_claim_review_history(
        self, claim_id: uuid.UUID
    ) -> list[PassportClaimReviewHistory]:
        """Fetch audit trail of all revisions and review decisions for a claim."""
        query = (
            select(PassportClaimReviewHistory)
            .where(PassportClaimReviewHistory.claim_id == claim_id)
            .order_by(PassportClaimReviewHistory.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def verify_claim(
        self, claim: PassportClaim, admin_id: uuid.UUID
    ) -> PassportClaim:
        """Mark claim as VERIFIED and record in review history."""
        claim.review_status = "VERIFIED"
        claim.reviewed_by_user_id = admin_id
        claim.reviewed_at = datetime.datetime.now(datetime.UTC)
        claim.rejection_reason = None

        history = PassportClaimReviewHistory(
            claim_id=claim.id,
            claim_scope=claim.claim_scope,
            claim_type=claim.claim_type,
            claim_key=claim.claim_key,
            claim_value=claim.claim_value,
            evidence_url=claim.evidence_url,
            evidence_type=claim.evidence_type,
            evidence_notes=claim.evidence_notes,
            is_public_evidence=claim.is_public_evidence,
            action="VERIFIED",
            review_status="VERIFIED",
            reviewer_id=admin_id,
            rejection_reason=None,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(claim)
        self.session.expire(claim, ["review_history"])
        return (await self.get_claim_by_id(claim.id)) or claim

    async def reject_claim(
        self, claim: PassportClaim, admin_id: uuid.UUID, rejection_reason: str
    ) -> PassportClaim:
        """Mark claim as REJECTED with mandatory reason and record in review history."""
        claim.review_status = "REJECTED"
        claim.reviewed_by_user_id = admin_id
        claim.reviewed_at = datetime.datetime.now(datetime.UTC)
        claim.rejection_reason = rejection_reason

        history = PassportClaimReviewHistory(
            claim_id=claim.id,
            claim_scope=claim.claim_scope,
            claim_type=claim.claim_type,
            claim_key=claim.claim_key,
            claim_value=claim.claim_value,
            evidence_url=claim.evidence_url,
            evidence_type=claim.evidence_type,
            evidence_notes=claim.evidence_notes,
            is_public_evidence=claim.is_public_evidence,
            action="REJECTED",
            review_status="REJECTED",
            reviewer_id=admin_id,
            rejection_reason=rejection_reason,
        )
        self.session.add(history)
        await self.session.flush()
        await self.session.refresh(claim)
        self.session.expire(claim, ["review_history"])
        return (await self.get_claim_by_id(claim.id)) or claim
        await self.session.flush()
        await self.session.refresh(claim)
        return claim
