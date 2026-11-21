import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuoteStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class DiscountType(enum.StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class Discount(Base):
    __tablename__ = "discounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    discount_type: Mapped[str] = mapped_column(
        String(20), default=DiscountType.PERCENTAGE.value, nullable=False
    )
    # If PERCENTAGE: basis points (e.g., 1000 = 10.00%, 2500 = 25.00%)
    # If FIXED_AMOUNT: amount in paise (e.g., 5000 = ₹50.00)
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(32), default="PLATFORM_WIDE", index=True, nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    times_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_order_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    max_discount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, index=True, nullable=False
    )
    valid_from: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        CheckConstraint("discount_value > 0", name="chk_discount_value_positive"),
        CheckConstraint(
            "discount_type IN ('PERCENTAGE', 'FIXED_AMOUNT')",
            name="chk_discount_type",
        ),
    )


class CheckoutQuote(Base):
    __tablename__ = "checkout_quotes"

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
    cart_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    delivery_address_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("addresses.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    delivery_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Version 2.0: the (normalised) discount code that applied to this quote.
    discount_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_total_paise: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    delivery_fee_paise: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    cgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    igst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tax_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_payable_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=QuoteStatus.ACTIVE.value, nullable=False
    )
    is_consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consumed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    superseded_by_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checkout_quotes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    items: Mapped[list["CheckoutQuoteItem"]] = relationship(
        "CheckoutQuoteItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="CheckoutQuoteItem.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_quote_ownership",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'CONSUMED', 'EXPIRED', 'SUPERSEDED')",
            name="chk_quote_status",
        ),
        CheckConstraint("subtotal_paise >= 0", name="chk_quote_subtotal_positive"),
        CheckConstraint(
            "discount_total_paise >= 0", name="chk_quote_discount_positive"
        ),
        CheckConstraint(
            "delivery_fee_paise >= 0", name="chk_quote_delivery_fee_positive"
        ),
        CheckConstraint("total_tax_paise >= 0", name="chk_quote_total_tax_positive"),
        CheckConstraint("total_payable_paise >= 0", name="chk_quote_payable_positive"),
        Index(
            "ix_quotes_customer_active",
            "customer_id",
            "status",
            postgresql_where=(status == QuoteStatus.ACTIVE.value),
        ),
        Index(
            "ix_quotes_guest_active",
            "guest_token_hash",
            "status",
            postgresql_where=(status == QuoteStatus.ACTIVE.value),
        ),
    )


class CheckoutQuoteItem(Base):
    __tablename__ = "checkout_quote_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checkout_quotes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("retailers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_title: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_title: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hsn_code: Mapped[str] = mapped_column(String(16), nullable=False)
    gst_rate_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_original_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_selling_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_discount_paise: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    unit_discounted_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_selling_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    taxable_base_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sgst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    igst_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tax_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    retailer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    retailer_state: Mapped[str] = mapped_column(String(100), nullable=False)
    # Version 2.0: ids (str) of the discounts priced into this line.
    applied_discount_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quote: Mapped["CheckoutQuote"] = relationship(
        "CheckoutQuote", back_populates="items"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_quote_item_quantity_positive"),
        CheckConstraint(
            "unit_original_price_paise >= 0",
            name="chk_quote_item_original_price_positive",
        ),
        CheckConstraint(
            "unit_selling_price_paise >= 0",
            name="chk_quote_item_selling_price_positive",
        ),
        CheckConstraint(
            "unit_discounted_price_paise >= 0",
            name="chk_quote_item_discounted_price_positive",
        ),
        CheckConstraint(
            "taxable_base_paise >= 0",
            name="chk_quote_item_taxable_base_positive",
        ),
    )


class DiscountRedemptionStatus(enum.StrEnum):
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"


class DiscountRedemption(Base):
    """One use of a discount by one order (Version 2.0).

    Created (RESERVED) with the order, incrementing ``discounts.times_used``
    under a row lock; set to RELEASED, decrementing it once, when an unpaid
    order is cancelled or its payment window expires."""

    __tablename__ = "discount_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    discount_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=DiscountRedemptionStatus.RESERVED.value,
        server_default=DiscountRedemptionStatus.RESERVED.value,
        nullable=False,
    )
    release_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    released_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "discount_id", "order_id", name="uq_discount_redemption_order"
        ),
        CheckConstraint(
            "status IN ('RESERVED', 'RELEASED')",
            name="chk_discount_redemption_status",
        ),
    )


class PriceAwardSource(enum.StrEnum):
    NEGOTIATION = "NEGOTIATION"
    GROUP_BUY = "GROUP_BUY"
    EXCHANGE = "EXCHANGE"
    AUCTION = "AUCTION"


class PriceAwardStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class PriceAward(Base):
    """A customer-specific, time-limited, single-use unit price for one listing.

    Phase 3 features that settle on a special price (AI Negotiator, Community
    Buying, Community Exchange RFQs, Dukaan vs Dukaan) issue awards instead of
    building their own checkout. The quote service applies the best ACTIVE award
    when it prices the customer's cart, so the negotiated price flows through the
    existing server-authoritative quote -> reservation -> order -> Razorpay pipeline. The award is
    marked USED when an order consumes the quote it was applied to.
    """

    __tablename__ = "price_awards"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=PriceAwardStatus.ACTIVE.value, nullable=False
    )
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    used_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("unit_price_paise > 0", name="chk_price_award_price_positive"),
        CheckConstraint("max_quantity > 0", name="chk_price_award_qty_positive"),
        Index("ix_price_awards_lookup", "customer_id", "listing_id", "status"),
        Index("ix_price_awards_source", "source", "source_id"),
        Index("ix_price_awards_quote", "quote_id"),
    )
