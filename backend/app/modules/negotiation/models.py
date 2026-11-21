import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NegotiationStatus(enum.StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class RetailerNegotiationRule(Base):
    """Retailer-configured limits the negotiator may never exceed."""

    __tablename__ = "retailer_negotiation_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=True,
    )
    min_floor_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_auto_discount_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    bundle_quantity_threshold: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    bundle_extra_discount_bps: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "max_auto_discount_bps >= 0 AND max_auto_discount_bps <= 5000",
            name="chk_neg_max_discount",
        ),
        CheckConstraint(
            "bundle_extra_discount_bps >= 0 AND bundle_extra_discount_bps <= 2000",
            name="chk_neg_bundle_discount",
        ),
        Index(
            "ix_negotiation_rules_retailer", "retailer_id", "listing_id", "is_active"
        ),
        Index(
            "uq_negotiation_rule_scope",
            "retailer_id",
            text("COALESCE(listing_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
    )


class NegotiationSession(Base):
    __tablename__ = "negotiation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    cart_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    target_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_budget_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    list_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    floor_total_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )  # never exposed
    current_round: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_rounds: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    proposed_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    final_accepted_price_paise: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(
        String(16), default=NegotiationStatus.IN_PROGRESS.value, nullable=False
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_negotiation_sessions_user", "user_id", "created_at"),)
