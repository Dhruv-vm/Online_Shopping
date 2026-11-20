import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceHistoryTick(Base):
    """Daily price snapshot per listing (Phase 3F Price Intelligence).

    One row per listing per calendar day (UTC). ``selling_price_paise`` is the
    latest price of the day, ``day_low_paise`` the lowest seen that day, so
    short-lived drops are not lost.
    """

    __tablename__ = "price_history_ticks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    recorded_date: Mapped[Any] = mapped_column(Date, nullable=False)
    selling_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    day_low_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mrp_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "listing_id", "recorded_date", name="uq_price_tick_listing_day"
        ),
        Index("ix_price_ticks_listing_date", "listing_id", "recorded_date"),
    )
