from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.catalogue.models import Product, ProductListing, Retailer
    from app.modules.identity.models import User


class ProductPassport(Base):
    """Canonical, product-level passport information."""

    __tablename__ = "product_passports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gtin_ean_upc: Mapped[str | None] = mapped_column(String(100), nullable=True)

    materials: Mapped[list[Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    technical_specs: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    package_contents: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    usage_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    warranty_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    certifications: Mapped[list[Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )

    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    product: Mapped[Product] = relationship("Product", foreign_keys=[product_id])
    claims: Mapped[list[PassportClaim]] = relationship(
        "PassportClaim",
        back_populates="passport",
        cascade="all, delete-orphan",
        order_by="PassportClaim.created_at.desc()",
    )


class ListingPassport(Base):
    """Retailer-listing-specific passport details (condition, warranty, packaging)."""

    __tablename__ = "listing_passports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_condition: Mapped[str] = mapped_column(
        String(50), default="NEW", nullable=False
    )
    seller_warranty: Mapped[str | None] = mapped_column(Text, nullable=True)
    packaging_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fulfillment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    listing: Mapped[ProductListing] = relationship(
        "ProductListing", foreign_keys=[listing_id]
    )
    retailer: Mapped[Retailer] = relationship("Retailer", foreign_keys=[retailer_id])
    claims: Mapped[list[PassportClaim]] = relationship(
        "PassportClaim",
        primaryjoin="ListingPassport.listing_id == foreign(PassportClaim.listing_id)",
        back_populates="listing_passport",
        cascade="all, delete-orphan",
        order_by="PassportClaim.created_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "item_condition IN ('NEW', 'REFURBISHED', 'OPEN_BOX', 'PRE_OWNED')",
            name="chk_listing_passport_condition",
        ),
    )


class PassportClaim(Base):
    """Claim and evidence record for canonical products or retailer listings."""

    __tablename__ = "passport_claims"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    passport_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_passports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    claim_scope: Mapped[str] = mapped_column(
        String(32), default="LISTING", index=True, nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_value: Mapped[str] = mapped_column(Text, nullable=False)

    evidence_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    evidence_type: Mapped[str] = mapped_column(
        String(64), default="DOCUMENT", nullable=False
    )
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public_evidence: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    review_status: Mapped[str] = mapped_column(
        String(32), default="PENDING", index=True, nullable=False
    )
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    passport: Mapped[ProductPassport | None] = relationship(
        "ProductPassport", back_populates="claims"
    )
    listing_passport: Mapped[ListingPassport | None] = relationship(
        "ListingPassport",
        primaryjoin="foreign(PassportClaim.listing_id) == ListingPassport.listing_id",
        back_populates="claims",
    )
    submitted_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[submitted_by_user_id]
    )
    reviewed_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[reviewed_by_user_id]
    )
    review_history: Mapped[list[PassportClaimReviewHistory]] = relationship(
        "PassportClaimReviewHistory",
        back_populates="claim",
        cascade="all, delete-orphan",
        order_by="desc(PassportClaimReviewHistory.created_at)",
    )

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="chk_passport_claim_status",
        ),
        CheckConstraint(
            "claim_scope IN ('PRODUCT', 'LISTING')",
            name="chk_passport_claim_scope",
        ),
        Index("ix_passport_claims_status_scope", "review_status", "claim_scope"),
    )


class PassportClaimReviewHistory(Base):
    """Immutable audit trail of claim submissions, revisions, and moderation decisions."""

    __tablename__ = "passport_claim_review_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("passport_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    claim_value: Mapped[str] = mapped_column(Text, nullable=False)

    evidence_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    evidence_type: Mapped[str] = mapped_column(
        String(64), default="DOCUMENT", nullable=False
    )
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public_evidence: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # SUBMITTED, REVISED, VERIFIED, REJECTED
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # PENDING, VERIFIED, REJECTED
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.datetime.now(datetime.UTC),
        nullable=False,
    )

    # Relationships
    claim: Mapped[PassportClaim] = relationship(
        "PassportClaim", back_populates="review_history"
    )
    reviewer: Mapped[User | None] = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('PENDING', 'VERIFIED', 'REJECTED')",
            name="chk_claim_review_history_status",
        ),
        CheckConstraint(
            "action IN ('SUBMITTED', 'VERIFIED', 'REJECTED', 'REVISED')",
            name="chk_claim_review_history_action",
        ),
        Index("ix_claim_review_history_claim_created", "claim_id", "created_at"),
    )
