from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.identity.models import User


class CustomerPreferenceProfile(Base):
    __tablename__ = "customer_preference_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preferred_brands: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    preferred_categories: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    preferred_retailers: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    preferred_price_range: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    preferred_attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    shopping_priorities: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    category_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    personalization_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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

    user: Mapped[User] = relationship("User", foreign_keys=[customer_id])


class RecurringIntention(Base):
    __tablename__ = "customer_recurring_intentions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category_ids: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    frequency: Mapped[str] = mapped_column(
        String(32), default="MONTHLY", nullable=False
    )  # WEEKLY, BIWEEKLY, MONTHLY, QUARTERLY, SEASONAL, CUSTOM
    budget_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_executed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    user: Mapped[User] = relationship("User", foreign_keys=[customer_id])


class IntentMemoryItem(Base):
    __tablename__ = "customer_intent_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[str] = mapped_column(
        String(64), default="PREFERENCE", nullable=False
    )  # PREFERENCE, RECURRING_GOAL, NOTE, CONTEXT
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[dict[str, Any] | str] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), default="CUSTOMER_STATED", nullable=False
    )  # CUSTOMER_STATED, MISSION_DERIVED, SYSTEM_SUGGESTED
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", foreign_keys=[customer_id])
