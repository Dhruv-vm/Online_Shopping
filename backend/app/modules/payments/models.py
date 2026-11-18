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
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


class PaymentProvider(enum.StrEnum):
    RAZORPAY_SANDBOX = "RAZORPAY_SANDBOX"
    RAZORPAY = "RAZORPAY"


class PaymentAttemptStatus(enum.StrEnum):
    CREATING = "CREATING"
    CREATION_AMBIGUOUS = "CREATION_AMBIGUOUS"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class CaptureStatus(enum.StrEnum):
    CAPTURED = "CAPTURED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class CaptureReconciliationStatus(enum.StrEnum):
    NORMAL = "NORMAL"
    OVERPAYMENT_ANOMALY = "OVERPAYMENT_ANOMALY"
    PARTIAL_CAPTURE_REJECTED = "PARTIAL_CAPTURE_REJECTED"
    LATE_CAPTURE_ANOMALY = "LATE_CAPTURE_ANOMALY"
    RESOLVED = "RESOLVED"


class RefundStatus(enum.StrEnum):
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUND_PROCESSED = "REFUND_PROCESSED"
    REFUND_FAILED = "REFUND_FAILED"


class WebhookEventStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    provider: Mapped[str] = mapped_column(
        String(32), default=PaymentProvider.RAZORPAY_SANDBOX.value, nullable=False
    )
    provider_order_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=PaymentAttemptStatus.CREATING.value,
        nullable=False,
        index=True,
    )
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
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

    order: Mapped[Any] = relationship("Order", back_populates="payments", lazy="raise")
    captures: Mapped[list["PaymentCapture"]] = relationship(
        "PaymentCapture",
        back_populates="payment",
        foreign_keys="[PaymentCapture.payment_id]",
        lazy="raise",
    )
    refunds: Mapped[list["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="payment",
        foreign_keys="[PaymentRefund.payment_id]",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "(customer_id IS NOT NULL AND guest_token_hash IS NULL) OR "
            "(customer_id IS NULL AND guest_token_hash IS NOT NULL)",
            name="chk_payment_ownership",
        ),
        CheckConstraint("amount_paise >= 0", name="chk_payment_amount_paise"),
        CheckConstraint(
            "status IN ('CREATING', 'CREATION_AMBIGUOUS', 'PENDING', 'AUTHORIZED', 'SUCCEEDED', 'FAILED', 'REQUIRES_RECONCILIATION', 'PARTIALLY_REFUNDED', 'REFUNDED')",
            name="chk_payment_status",
        ),
        UniqueConstraint(
            "order_id", "idempotency_key", name="uq_payments_order_idempotency"
        ),
        UniqueConstraint(
            "order_id", "attempt_number", name="uq_payments_order_attempt"
        ),
        UniqueConstraint("id", "order_id", name="uq_payments_id_order"),
    )


class PaymentCapture(Base):
    __tablename__ = "payment_captures"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32), default=PaymentProvider.RAZORPAY_SANDBOX.value, nullable=False
    )
    provider_payment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=CaptureStatus.CAPTURED.value, nullable=False
    )
    method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    acquirer_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_fulfillment_eligible: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    reconciliation_status: Mapped[str] = mapped_column(
        String(32),
        default=CaptureReconciliationStatus.NORMAL.value,
        nullable=False,
        index=True,
    )
    captured_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
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

    payment: Mapped["Payment"] = relationship(
        "Payment", back_populates="captures", foreign_keys=[payment_id], lazy="raise"
    )
    order: Mapped[Any] = relationship(
        "Order", foreign_keys=[order_id], overlaps="fulfilling_capture", lazy="raise"
    )
    refunds: Mapped[list["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="capture",
        foreign_keys="[PaymentRefund.capture_id]",
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_payment_captures_provider_payment",
        ),
        UniqueConstraint("id", "order_id", name="uq_payment_captures_id_order"),
        ForeignKeyConstraint(
            ["payment_id", "order_id"],
            ["payments.id", "payments.order_id"],
            name="fk_payment_captures_payment_same_order",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount_paise > 0", name="chk_capture_amount_paise"),
        CheckConstraint(
            "reconciliation_status IN ('NORMAL', 'OVERPAYMENT_ANOMALY', 'PARTIAL_CAPTURE_REJECTED', 'LATE_CAPTURE_ANOMALY', 'RESOLVED')",
            name="chk_capture_reconciliation_status",
        ),
    )


class PaymentRefund(Base):
    __tablename__ = "payment_refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    capture_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payment_captures.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider_refund_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=RefundStatus.REFUND_REQUESTED.value,
        nullable=False,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
    )
    processed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    capture: Mapped["PaymentCapture"] = relationship(
        "PaymentCapture",
        back_populates="refunds",
        foreign_keys=[capture_id],
        lazy="raise",
    )
    payment: Mapped["Payment"] = relationship(
        "Payment", back_populates="refunds", foreign_keys=[payment_id], lazy="raise"
    )
    order: Mapped[Any] = relationship(
        "Order", foreign_keys=[order_id], overlaps="fulfilling_capture", lazy="raise"
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["capture_id", "order_id"],
            ["payment_captures.id", "payment_captures.order_id"],
            name="fk_refunds_capture_same_order",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payment_id", "order_id"],
            ["payments.id", "payments.order_id"],
            name="fk_refunds_payment_same_order",
            ondelete="RESTRICT",
        ),
        CheckConstraint("amount_paise > 0", name="chk_refund_amount_paise"),
        CheckConstraint(
            "status IN ('REFUND_REQUESTED', 'REFUND_PENDING', 'REFUND_PROCESSED', 'REFUND_FAILED')",
            name="chk_refund_status",
        ),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(
        String(32), default=PaymentProvider.RAZORPAY.value, nullable=False
    )
    provider_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=Text()).with_variant(JSON(), "sqlite"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=WebhookEventStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claim_expires_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Any | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_provider_event"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'PROCESSED', 'IGNORED', 'FAILED')",
            name="chk_webhook_status",
        ),
        Index("ix_webhook_claim", "status", "claim_expires_at"),
        Index("ix_webhook_created", "created_at"),
    )
