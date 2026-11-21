"""Recurring basket schedule and its per-date preparation runs.

No payment data lives here: a recurring basket never charges anyone. Each
scheduled date produces one *run* (a pre-order check the customer reviews).
"""

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSONB(astext_type=Text()).with_variant(JSON(), "sqlite")


class RecurringBasket(Base):
    __tablename__ = "recurring_baskets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # [{listing_id, quantity, product_name, variant_name, retailer_name}]
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..28
    start_date: Mapped[Any] = mapped_column(Date, nullable=False)
    end_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    delivery_address_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("addresses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # ACTIVE | PAUSED | CANCELLED | ENDED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    skip_dates: Mapped[list[str]] = mapped_column(
        JSONType, nullable=False, default=list, server_default="[]"
    )
    next_run_date: Mapped[Any | None] = mapped_column(Date, nullable=True, index=True)
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
        CheckConstraint(
            "day_of_month BETWEEN 1 AND 28", name="ck_recurring_baskets_day"
        ),
    )


class RecurringBasketRun(Base):
    __tablename__ = "recurring_basket_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recurring_basket_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("recurring_baskets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_for: Mapped[Any] = mapped_column(Date, nullable=False)
    # PREPARED (checked, waiting for the customer) | LOADED_TO_CART | SKIPPED
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    check: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
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
        UniqueConstraint(
            "recurring_basket_id", "scheduled_for", name="uq_recurring_basket_run_date"
        ),
    )
