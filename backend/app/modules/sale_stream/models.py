import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SaleStreamEventType(enum.StrEnum):
    PRICE_DROP = "PRICE_DROP"
    FLASH_DEAL = "FLASH_DEAL"
    HOT_SELLER = "HOT_SELLER"


class SaleStreamEvent(Base):
    """A time-boxed entry in the live Sale Stream feed (Phase 3G).

    Sale Stream Rewind (replaying expired events) is permanently out of scope:
    the feed only ever serves events whose window is currently open.
    """

    __tablename__ = "sale_stream_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
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
    discount_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    old_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    flash_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stock_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    units_sold_24h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    starts_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_sale_stream_live", "status", "expires_at", "created_at"),
        Index("ix_sale_stream_listing", "listing_id", "event_type", "status"),
    )
