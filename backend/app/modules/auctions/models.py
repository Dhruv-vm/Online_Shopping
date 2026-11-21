import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuctionStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"  # ended with bids, awaiting customer choice
    NO_BIDS = "NO_BIDS"
    AWARDED = "AWARDED"
    CANCELLED = "CANCELLED"


class BasketAuction(Base):
    __tablename__ = "basket_auctions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    cart_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    reference_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=AuctionStatus.ACTIVE.value, nullable=False
    )
    winning_bid_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    starts_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_basket_auctions_live", "status", "pincode", "ends_at"),
        Index("ix_basket_auctions_user", "user_id", "status"),
    )


class BasketAuctionBid(Base):
    __tablename__ = "basket_auction_bids"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    auction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("basket_auctions.id", ondelete="CASCADE"),
        nullable=False,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
    )
    bid_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivery_eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warranty_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    line_allocation: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_auction_bids_rank",
            "auction_id",
            "bid_price_paise",
            "delivery_eta_minutes",
        ),
    )
