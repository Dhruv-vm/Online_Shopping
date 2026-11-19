import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


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
    payment_window_expires_at: datetime
    created_at: datetime
    items: list[OrderItemResponse]

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
    created_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderListItemResponse]
    total: int
