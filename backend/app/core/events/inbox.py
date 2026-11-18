from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InboxStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class ConsumerInbox(Base):
    """
    Durable deduplication table providing effectively-once consumer side effects
    across worker crashes and at-least-once Kafka deliveries.
    """

    __tablename__ = "consumer_inbox"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    consumer_group: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    aggregate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=InboxStatus.PENDING.value, nullable=False
    )
    first_seen_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dlq_published_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "consumer_group", "event_id", name="uq_consumer_inbox_group_event"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'DEAD_LETTER')",
            name="chk_consumer_inbox_status",
        ),
        Index("ix_consumer_inbox_group_event", "consumer_group", "event_id"),
        Index(
            "ix_consumer_inbox_aggregate",
            "aggregate_type",
            "aggregate_id",
            "aggregate_version",
        ),
        Index("ix_consumer_inbox_retention", "status", "processed_at"),
        Index(
            "ix_consumer_inbox_retry",
            "consumer_group",
            "status",
            "next_attempt_at",
        ),
    )


class OrderSummaryProjection(Base):
    """
    Authoritative read-model projection maintained by OrderProjectionConsumer
    demonstrating Strategy A ACID atomic mutations.
    """

    __tablename__ = "order_summary_projections"

    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(32), default="NOT_INITIATED", nullable=False
    )
    total_payable_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    last_aggregate_version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
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
        Index("ix_order_projections_status", "status"),
        Index("ix_order_projections_customer", "customer_id"),
    )


async def get_inbox_record(
    session: AsyncSession,
    consumer_group: str,
    event_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> ConsumerInbox | None:
    """Fetch an existing consumer inbox record by consumer_group and event_id."""
    stmt = select(ConsumerInbox).where(
        ConsumerInbox.consumer_group == consumer_group,
        ConsumerInbox.event_id == event_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
