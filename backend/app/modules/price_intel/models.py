import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
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
    # LIVE = recorded from real price changes; DEMO_SEED = demonstration data
    # created by the demo seed (always labelled as such in the API/UI).
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="LIVE", server_default=text("'LIVE'")
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "listing_id", "recorded_date", name="uq_price_tick_listing_day"
        ),
        Index("ix_price_ticks_listing_date", "listing_id", "recorded_date"),
        CheckConstraint(
            "source IN ('LIVE', 'DEMO_SEED')", name="chk_price_tick_source"
        ),
    )


class PriceAlert(Base):
    """Customer request to be notified when a variant drops to a target price."""

    __tablename__ = "price_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default=text("'ACTIVE'")
    )
    triggered_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    triggered_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    triggered_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("target_price_paise > 0", name="chk_price_alert_target"),
        CheckConstraint(
            "status IN ('ACTIVE', 'TRIGGERED', 'CANCELLED')",
            name="chk_price_alert_status",
        ),
        Index(
            "uq_price_alert_active",
            "user_id",
            "variant_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_price_alert_variant_status", "variant_id", "status"),
    )
