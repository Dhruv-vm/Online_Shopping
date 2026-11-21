import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class DeliveryAddressInput(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    address_line1: str = Field(..., min_length=5, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., description="6-digit Indian PIN code")
    phone: str = Field(..., description="Valid 10-digit Indian phone number")

    @field_validator("postal_code")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^[1-9][0-9]{5}$", clean):
            raise ValueError(
                "Invalid Indian PIN code. Must be 6 digits and cannot start with 0."
            )
        return clean

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = re.sub(r"[\s\-\(\)]", "", v.strip())
        if clean.startswith("+91"):
            clean = clean[3:]
        elif clean.startswith("0"):
            clean = clean[1:]
        if not re.match(r"^[6-9]\d{9}$", clean):
            raise ValueError(
                "Invalid Indian phone number. Must be a 10-digit mobile number starting with 6-9."
            )
        return f"+91{clean}"


class CreateOrderRequest(BaseModel):
    quote_id: uuid.UUID | None = None
    reservation_id: uuid.UUID
    delivery_address_id: uuid.UUID | None = None
    delivery_address: DeliveryAddressInput | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)

    @field_validator("quote_id", mode="before")
    @classmethod
    def clean_empty_quote_id(cls, v: Any) -> Any:
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("delivery_address_id", mode="before")
    @classmethod
    def clean_empty_address_id(cls, v: Any) -> Any:
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def clean_empty_idempotency_key(cls, v: Any) -> Any:
        if v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    variant_id: uuid.UUID
    retailer_id: uuid.UUID
    product_title: str
    variant_title: str
    sku: str | None
    hsn_code: str
    gst_rate_basis_points: int
    quantity: int
    unit_original_price_paise: int
    unit_selling_price_paise: int
    unit_discount_paise: int
    unit_discounted_price_paise: int
    total_selling_price_paise: int
    taxable_base_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    retailer_name: str
    retailer_state: str
    fulfillment_status: str = Field(default="CONFIRMED")


class OrderStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str | None
    to_status: str
    reason: str | None
    created_at: datetime


class ShipmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_item_id: uuid.UUID
    quantity: int
    created_at: datetime


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    shipment_number: str
    carrier_name: str
    carrier_code: str
    tracking_number: str
    tracking_url: str | None
    status: str
    shipped_at: datetime | None
    estimated_delivery_at: datetime | None
    delivered_at: datetime | None
    notes: str | None
    carrier_event_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    items: list[ShipmentItemResponse] = Field(default_factory=list)


class ReturnItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_item_id: uuid.UUID
    quantity: int
    refund_subtotal_paise: int
    condition_grade: str | None
    restock_approved: bool
    created_at: datetime


class ReturnStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str | None
    to_status: str
    reason: str | None
    actor: str
    created_at: datetime


class ReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    return_number: str
    status: str
    reason: str
    customer_notes: str | None
    admin_notes: str | None
    refund_amount_paise: int
    payment_refund_id: uuid.UUID | None
    requested_at: datetime
    inspected_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    items: list[ReturnItemResponse] = Field(default_factory=list)
    status_history: list[ReturnStatusHistoryResponse] = Field(default_factory=list)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    order_number: str
    customer_id: uuid.UUID | None
    quote_id: uuid.UUID
    reservation_id: uuid.UUID
    delivery_address_snapshot: dict[str, Any]
    subtotal_paise: int
    discount_total_paise: int
    delivery_fee_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    total_payable_paise: int
    currency: str
    status: str
    payment_status: str
    guest_access_token: str | None = None
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    delivered_at: datetime | None = None
    payment_window_expires_at: datetime
    created_at: datetime
    items: list[OrderItemResponse] = Field(default_factory=list)
    status_history: list[OrderStatusHistoryResponse] = Field(default_factory=list)
    shipments: list[ShipmentResponse] = Field(default_factory=list)
    returns: list[ReturnResponse] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def populate_defaults_for_unloaded(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        from sqlalchemy import inspect
        from sqlalchemy.orm.base import NO_VALUE

        insp = inspect(data, raiseerr=False)
        if insp:
            res: dict[str, Any] = {}
            for col in data.__table__.columns:
                res[col.name] = getattr(data, col.name)
            for rel in ("items", "status_history", "shipments", "returns"):
                if rel in insp.attrs and insp.attrs[rel].loaded_value is not NO_VALUE:
                    res[rel] = getattr(data, rel)
                else:
                    res[rel] = []
            res["delivery_address_snapshot"] = data.delivery_address_snapshot
            res["guest_access_token"] = getattr(data, "guest_access_token", None)
            return res
        return data

    @computed_field
    @property
    def delivery_address(self) -> dict[str, Any]:
        return self.delivery_address_snapshot


class OrderListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_number: str
    status: str
    payment_status: str
    total_payable_paise: int
    currency: str
    item_count: int
    cancellation_reason: str | None = None
    cancelled_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderListItemResponse]
    total: int

    @computed_field
    @property
    def orders(self) -> list[OrderListItemResponse]:
        return self.items


class OrderCancellationRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=128)


class OrderCancellationResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    status: str
    cancelled_at: datetime
    refund_status: str | None = None
    refund_amount_paise: int | None = None
    inventory_restocked: bool
    message: str


class CreateShipmentItemInput(BaseModel):
    order_item_id: uuid.UUID
    quantity: int = Field(..., gt=0)


class CreateShipmentRequest(BaseModel):
    carrier_name: str = Field(..., min_length=2, max_length=64)
    carrier_code: str = Field(..., min_length=2, max_length=32)
    tracking_number: str = Field(..., min_length=2, max_length=64)
    tracking_url: str | None = Field(default=None, max_length=512)
    estimated_delivery_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)
    items: list[CreateShipmentItemInput] | None = None


class UpdateShipmentStatusRequest(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=500)


class OrderTrackingTimelineEvent(BaseModel):
    status: str
    title: str
    description: str
    timestamp: datetime | None = None
    completed: bool = False
    current: bool = False


class OrderTrackingResponse(BaseModel):
    order_id: uuid.UUID
    order_number: str
    order_status: str
    carrier_name: str | None = None
    carrier_code: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    estimated_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    shipments: list[ShipmentResponse] = Field(default_factory=list)
    timeline: list[OrderTrackingTimelineEvent] = Field(default_factory=list)


class ReturnItemCreateRequest(BaseModel):
    order_item_id: uuid.UUID
    quantity: int = Field(..., gt=0)


class ReturnCreateRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)
    customer_notes: str | None = Field(default=None, max_length=1000)
    items: list[ReturnItemCreateRequest] = Field(..., min_length=1)
    idempotency_key: str | None = Field(default=None, max_length=128)


class ReturnStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    admin_notes: str | None = Field(default=None, max_length=1000)
    restock_approved: bool | None = None


class GuestOrderLookupRequest(BaseModel):
    order_number: str = Field(..., min_length=3, max_length=32)
    access_token: str = Field(..., min_length=16, max_length=128)


class CustomerNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID | None
    title: str
    message: str
    event_type: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[CustomerNotificationResponse]
    unread_count: int
