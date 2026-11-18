import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentInitiateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: uuid.UUID
    order_id: uuid.UUID
    order_number: str
    provider: str
    provider_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str
    status: str
    attempt_number: int
    payment_window_expires_at: datetime


class PaymentVerifyRequest(BaseModel):
    payment_id: uuid.UUID | None = None
    razorpay_payment_id: str = Field(..., min_length=1, max_length=128)
    razorpay_order_id: str = Field(..., min_length=1, max_length=128)
    razorpay_signature: str = Field(..., min_length=1, max_length=128)


class PaymentVerifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    payment_status: str
    order_id: uuid.UUID
    order_number: str
    fulfilling_capture_id: uuid.UUID | None = None
    amount_paid_paise: int
    confirmed_at: datetime | None = None


class WebhookIngestResponse(BaseModel):
    status: str
    event_id: str | None = None
    reason: str | None = None


class CreateRefundRequest(BaseModel):
    capture_id: uuid.UUID | None = None
    amount_paise: int = Field(..., gt=0)
    reason: str | None = Field(None, max_length=255)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    refund_id: uuid.UUID
    capture_id: uuid.UUID
    payment_id: uuid.UUID
    order_id: uuid.UUID
    provider_refund_id: str | None = None
    amount_paise: int
    currency: str
    status: str


class ReconcilePendingRequest(BaseModel):
    batch_size: int = Field(50, ge=1, le=500)
    max_age_minutes: int = Field(1440, ge=1)


class ReconcilePendingResponse(BaseModel):
    reconciled_payments_count: int
    reconciled_webhooks_count: int
    ambiguous_attempts_resolved: int


class ResolveAmbiguityRequest(BaseModel):
    action: str = Field(..., pattern="^(CONFIRM_ABSENT|LINK_PROVIDER_ORDER)$")
    provider_order_id: str | None = Field(None, max_length=128)


class ResolveAmbiguityResponse(BaseModel):
    payment_id: uuid.UUID
    status: str
    action_taken: str
    resolved_at: datetime
