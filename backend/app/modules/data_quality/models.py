"""Reversible quarantine ledger for test fixtures found in non-test databases."""

import uuid
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataQuarantine(Base):
    """One row per record hidden by a quarantine batch.

    ``previous_state`` stores the original column values so a batch can be
    restored exactly (``python -m app.seeds.quarantine_test_data --restore``).
    """

    __tablename__ = "data_quarantine"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(48), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    previous_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    restored_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_data_quarantine_batch", "batch_id"),
        Index("ix_data_quarantine_entity", "entity_type", "entity_id"),
    )
