import enum
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


class OrderStatus(enum.StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class ShipmentStatus(enum.StrEnum):
    LABEL_CREATED = "LABEL_CREATED"
    PICKED_UP = "PICKED_UP"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    EXCEPTION = "EXCEPTION"
    CANCELLED = "CANCELLED"


class ReturnStatus(enum.StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PICKUP_PENDING = "PICKUP_PENDING"
    RECEIVED = "RECEIVED"
    INSPECTED = "INSPECTED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentStatus(enum.StrEnum):
    NOT_INITIATED = "NOT_INITIATED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class OutboxStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    guest_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    guest_access_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("checkout_quotes.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    reservation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("inventory_reservations.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    delivery_address_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
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
        String(32),
        default=OrderStatus.PENDING_PAYMENT.value,
        nullable=False,
        index=True,
    )
    payment_status: Mapped[str] = mapped_column(
        String(32),
        default=PaymentStatus.NOT_INITIATED.value,
        nullable=False,
        index=True,
    )
    fulfilling_capture_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        unique=True,
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payment_window_expires_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(
        Integer, server_default="1", default=1, nullable=False
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.created_at",
        lazy="selectin",
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusHistory.created_at",
        lazy="selectin",
    )
    shipments: Mapped[list["Shipment"]] = relationship(
        "Shipment",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Shipment.created_at",
        lazy="selectin",
    )
    returns: Mapped[list["OrderReturn"]] = relationship(
        "OrderReturn",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderReturn.created_at",
        lazy="selectin",
    )
    quote: Mapped[Any] = relationship("CheckoutQuote")
    reservation: Mapped[Any] = relationship(
        "InventoryReservation", foreign_keys=[reservation_id]
    )
    payments: Mapped[list[Any]] = relationship(
        "Payment",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="Payment.created_at",
    )
    fulfilling_capture: Mapped[Any] = relationship(
        "PaymentCapture",
        primaryjoin="and_(Order.fulfilling_capture_id == foreign(PaymentCapture.id), Order.id == foreign(PaymentCapture.order_id))",
        uselist=False,
        post_update=True,
        viewonly=True,
        lazy="raise",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["fulfilling_capture_id", "id"],
            ["payment_captures.id", "payment_captures.order_id"],
            name="fk_orders_fulfilling_capture_same_order",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_order_ownership",
        ),
        CheckConstraint(
            "status IN ('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED')",
            name="chk_order_status",
        ),
        CheckConstraint(
            "payment_status IN ('NOT_INITIATED', 'PENDING', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')",
            name="chk_order_payment_status",
        ),
        CheckConstraint("subtotal_paise >= 0", name="chk_order_subtotal_paise"),
        CheckConstraint(
            "total_payable_paise >= 0", name="chk_order_total_payable_paise"
        ),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
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
    fulfillment_status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.CONFIRMED.value,
        server_default="CONFIRMED",
        nullable=False,
        index=True,
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    shipment_items: Mapped[list["ShipmentItem"]] = relationship(
        "ShipmentItem", back_populates="order_item"
    )
    return_items: Mapped[list["ReturnItem"]] = relationship(
        "ReturnItem", back_populates="order_item"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_order_item_quantity"),
        CheckConstraint(
            "unit_selling_price_paise >= 0",
            name="chk_order_item_unit_selling_price_paise",
        ),
        CheckConstraint(
            "total_selling_price_paise >= 0",
            name="chk_order_item_total_selling_price_paise",
        ),
        CheckConstraint(
            "fulfillment_status IN ('PENDING_PAYMENT', 'CONFIRMED', 'PROCESSING', 'PACKED', 'SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'CANCELLED', 'RETURNED')",
            name="chk_order_item_fulfillment_status",
        ),
    )


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_history")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), default=OutboxStatus.PENDING.value, nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    published_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claim_expires_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aggregate_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PUBLISHED', 'FAILED')",
            name="chk_outbox_status",
        ),
        Index(
            "ix_outbox_pending",
            "created_at",
            postgresql_where=text("status = 'PENDING'"),
            sqlite_where=text("status = 'PENDING'"),
        ),
        Index(
            "ix_outbox_lease_poll",
            "status",
            "next_attempt_at",
            "claim_expires_at",
            postgresql_where=text("status IN ('PENDING', 'PROCESSING')"),
            sqlite_where=text("status IN ('PENDING', 'PROCESSING')"),
        ),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)

    order: Mapped["Order"] = relationship("Order")

    __table_args__ = (
        CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_idempotency_ownership",
        ),
        Index(
            "uq_idempotency_customer",
            "scope",
            "customer_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("customer_id IS NOT NULL"),
            sqlite_where=text("customer_id IS NOT NULL"),
        ),
        Index(
            "uq_idempotency_guest",
            "scope",
            "guest_token_hash",
            "idempotency_key",
            unique=True,
            postgresql_where=text("guest_token_hash IS NOT NULL"),
            sqlite_where=text("guest_token_hash IS NOT NULL"),
        ),
    )


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shipment_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    carrier_name: Mapped[str] = mapped_column(String(64), nullable=False)
    carrier_code: Mapped[str] = mapped_column(String(32), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tracking_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ShipmentStatus.LABEL_CREATED.value,
        server_default="LABEL_CREATED",
        nullable=False,
        index=True,
    )
    shipped_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_delivery_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    carrier_event_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=list,
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

    order: Mapped["Order"] = relationship("Order", back_populates="shipments")
    items: Mapped[list["ShipmentItem"]] = relationship(
        "ShipmentItem", back_populates="shipment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('LABEL_CREATED', 'PICKED_UP', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'EXCEPTION', 'CANCELLED')",
            name="chk_shipment_status",
        ),
    )


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="items")
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="shipment_items"
    )

    __table_args__ = (CheckConstraint("quantity > 0", name="chk_shipment_item_qty"),)


class OrderReturn(Base):
    __tablename__ = "order_returns"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    return_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    guest_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReturnStatus.REQUESTED.value,
        server_default="REQUESTED",
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount_paise: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0", nullable=False
    )
    payment_refund_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payment_refunds.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    requested_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    inspected_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Any | None] = mapped_column(
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

    order: Mapped["Order"] = relationship("Order", back_populates="returns")
    items: Mapped[list["ReturnItem"]] = relationship(
        "ReturnItem", back_populates="return_order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["ReturnStatusHistory"]] = relationship(
        "ReturnStatusHistory",
        back_populates="return_order",
        cascade="all, delete-orphan",
        order_by="ReturnStatusHistory.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'PICKUP_PENDING', 'RECEIVED', 'INSPECTED', 'REFUND_PENDING', 'REFUNDED', 'CANCELLED')",
            name="chk_return_status",
        ),
        CheckConstraint("refund_amount_paise >= 0", name="chk_return_refund_amount"),
    )


class ReturnItem(Base):
    __tablename__ = "return_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    return_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_subtotal_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    condition_grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    restock_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    return_order: Mapped["OrderReturn"] = relationship(
        "OrderReturn", back_populates="items"
    )
    order_item: Mapped["OrderItem"] = relationship(
        "OrderItem", back_populates="return_items"
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_return_item_qty"),
        CheckConstraint(
            "refund_subtotal_paise >= 0", name="chk_return_item_refund_subtotal"
        ),
    )


class ReturnStatusHistory(Base):
    __tablename__ = "return_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    return_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("order_returns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor: Mapped[str] = mapped_column(
        String(64), default="CUSTOMER", server_default="CUSTOMER", nullable=False
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    return_order: Mapped["OrderReturn"] = relationship(
        "OrderReturn", back_populates="status_history"
    )


class CustomerNotification(Base):
    __tablename__ = "customer_notifications"

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
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False, index=True
    )
    read_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
