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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExchangeRequestStatus(enum.StrEnum):
    BIDDING_OPEN = "BIDDING_OPEN"
    AWARDED = "AWARDED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ExchangeBidStatus(enum.StrEnum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ExchangeRequest(Base):
    __tablename__ = "exchange_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    delivery_pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    budget_limit_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    items_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ExchangeRequestStatus.BIDDING_OPEN.value, nullable=False
    )
    accepted_bid_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_exchange_requests_open", "status", "delivery_pincode", "expires_at"),
        Index("ix_exchange_requests_user", "user_id", "created_at"),
    )


class ExchangeBid(Base):
    __tablename__ = "exchange_bids"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("exchange_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
    )
    bid_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_delivery_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    items_covered: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ExchangeBidStatus.SUBMITTED.value, nullable=False
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

    __table_args__ = (
        UniqueConstraint("request_id", "retailer_id", name="uq_exchange_bid_retailer"),
    )
