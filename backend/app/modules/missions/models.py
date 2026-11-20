import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.catalogue.models import (
        Category,
        Product,
        ProductListing,
        ProductVariant,
        Retailer,
    )
    from app.modules.identity.models import User


class ShoppingMission(Base):
    __tablename__ = "shopping_missions"

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    people_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    preferences: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    excluded_brands: Mapped[list[str]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False, index=True
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

    # Relationships
    customer: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
    category: Mapped["Category | None"] = relationship("Category")  # type: ignore[name-defined]
    items: Mapped[list["ShoppingMissionItem"]] = relationship(
        "ShoppingMissionItem",
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="ShoppingMissionItem.sort_order.asc()",
    )

    __table_args__ = (
        CheckConstraint(
            "budget_paise > 0", name="chk_shopping_mission_budget_positive"
        ),
        CheckConstraint(
            "people_count >= 1", name="chk_shopping_mission_people_positive"
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SAVED', 'COMPLETED', 'ARCHIVED')",
            name="chk_shopping_mission_status",
        ),
    )


class ShoppingMissionItem(Base):
    __tablename__ = "shopping_mission_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shopping_missions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_name: Mapped[str] = mapped_column(
        String(100), default="Essentials", nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    mission: Mapped["ShoppingMission"] = relationship(
        "ShoppingMission", back_populates="items"
    )
    product: Mapped["Product"] = relationship("Product")  # type: ignore[name-defined]
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")  # type: ignore[name-defined]
    listing: Mapped["ProductListing"] = relationship("ProductListing")  # type: ignore[name-defined]
    retailer: Mapped["Retailer"] = relationship("Retailer")  # type: ignore[name-defined]

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="chk_mission_item_quantity_positive"),
        CheckConstraint(
            "unit_price_paise >= 0",
            name="chk_mission_item_unit_price_nonnegative",
        ),
    )
