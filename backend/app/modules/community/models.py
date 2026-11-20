import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GroupBuyStatus(enum.StrEnum):
    OPEN = "OPEN"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GroupBuyMemberStatus(enum.StrEnum):
    JOINED = "JOINED"
    LEFT = "LEFT"
    AWARDED = "AWARDED"
    PURCHASED = "PURCHASED"
    NOT_FULFILLED = "NOT_FULFILLED"


class GroupBuyCampaign(Base):
    __tablename__ = "group_buy_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    min_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    current_participants: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_quantity_per_member: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False
    )
    discount_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    list_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    group_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=GroupBuyStatus.OPEN.value, nullable=False
    )
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("min_participants >= 2", name="chk_gb_min"),
        CheckConstraint("max_participants >= min_participants", name="chk_gb_max"),
        CheckConstraint(
            "current_participants >= 0 AND current_participants <= max_participants",
            name="chk_gb_current",
        ),
        CheckConstraint(
            "discount_bps > 0 AND discount_bps <= 9000", name="chk_gb_discount"
        ),
        CheckConstraint("group_price_paise > 0", name="chk_gb_price"),
        Index("ix_group_buy_status_expiry", "status", "expires_at"),
        Index("ix_group_buy_retailer", "retailer_id", "status"),
    )


class GroupBuyMember(Base):
    __tablename__ = "group_buy_members"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("group_buy_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=GroupBuyMemberStatus.JOINED.value, nullable=False
    )
    award_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    joined_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", name="uq_group_buy_member"),
        CheckConstraint("quantity > 0", name="chk_gb_member_qty"),
        Index("ix_group_buy_members_award", "award_id"),
    )
