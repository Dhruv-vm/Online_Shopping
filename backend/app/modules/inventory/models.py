import enum
import uuid
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ReservationStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CONFIRMED = "CONFIRMED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    guest_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checkout_quotes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default=ReservationStatus.ACTIVE.value, nullable=False, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    expires_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    confirmed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    released_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list["InventoryReservationItem"]] = relationship(
        "InventoryReservationItem",
        back_populates="reservation",
        cascade="all, delete-orphan",
        order_by="InventoryReservationItem.created_at",
    )
    quote: Mapped[Any] = relationship("CheckoutQuote")

    __table_args__ = (
        CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_reservation_ownership",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'CONFIRMED', 'RELEASED', 'EXPIRED')",
            name="chk_reservation_status",
        ),
        Index("ix_reservations_status_expires", "status", "expires_at"),
        Index(
            "uq_reservations_quote_active",
            "quote_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_reservations_customer_idempotency",
            "customer_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text(
                "customer_id IS NOT NULL AND idempotency_key IS NOT NULL"
            ),
            sqlite_where=text(
                "customer_id IS NOT NULL AND idempotency_key IS NOT NULL"
            ),
        ),
        Index(
            "uq_reservations_guest_idempotency",
            "guest_token_hash",
            "idempotency_key",
            unique=True,
            postgresql_where=text(
                "guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL"
            ),
            sqlite_where=text(
                "guest_token_hash IS NOT NULL AND idempotency_key IS NOT NULL"
            ),
        ),
    )


class InventoryReservationItem(Base):
    __tablename__ = "inventory_reservation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reservation: Mapped["InventoryReservation"] = relationship(
        "InventoryReservation", back_populates="items"
    )
    listing: Mapped[Any] = relationship("ProductListing")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_reservation_item_quantity_positive"),
        Index(
            "uq_reservation_listing",
            "reservation_id",
            "listing_id",
            unique=True,
        ),
    )
