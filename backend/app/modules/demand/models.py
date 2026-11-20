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
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DemandSignalType(enum.StrEnum):
    ZERO_SEARCH = "ZERO_SEARCH"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    WISHLIST = "WISHLIST"  # explicit "Request product / Notify me"


class DemandPoolStatus(enum.StrEnum):
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    EXPIRED = "EXPIRED"


class DemandPool(Base):
    __tablename__ = "demand_pools"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    normalized_product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    total_demand_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_users_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    visibility_threshold: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=DemandPoolStatus.OPEN.value, nullable=False
    )
    last_signal_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    fulfilled_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_demand_pools_key", "normalized_product_name", "pincode", "status"),
        Index("ix_demand_pools_status_activity", "status", "last_signal_at"),
        Index(
            "uq_demand_pool_open",
            "normalized_product_name",
            text("COALESCE(pincode, '')"),
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )


class DemandSignal(Base):
    __tablename__ = "demand_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("demand_pools.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    query_text: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="SET NULL"),
        nullable=True,
    )
    pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    signal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_demand_signals_pool_user", "pool_id", "user_id"),
        Index("ix_demand_signals_pool_guest", "pool_id", "guest_token_hash"),
        Index("ix_demand_signals_created", "created_at"),
    )


class DemandPoolResponse(Base):
    """A retailer's commitment to stock/supply a demand pool."""

    __tablename__ = "demand_pool_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("demand_pools.id", ondelete="CASCADE"),
        nullable=False,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    offered_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("pool_id", "retailer_id", name="uq_demand_response_retailer"),
    )
