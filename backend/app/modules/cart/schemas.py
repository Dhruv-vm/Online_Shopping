import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CartItemAddRequest(BaseModel):
    listing_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=10)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=10)


class CartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    variant_name: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    primary_image_url: str | None = None
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_rating: float | None = None
    unit_price_paise: int
    quantity: int
    subtotal_paise: int
    available_stock: int
    is_available: bool
    validation_message: str | None = None
    created_at: datetime
    updated_at: datetime


class CartRetailerSummary(BaseModel):
    retailer_id: uuid.UUID
    retailer_name: str
    item_count: int
    subtotal_paise: int


class CartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    currency: str
    items: list[CartItemResponse] = Field(default_factory=list)
    item_count: int = 0
    total_quantity: int = 0
    subtotal_paise: int = 0
    retailers: list[CartRetailerSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CartMergeRequest(BaseModel):
    guest_token: str | None = None


class CartMergeResponse(BaseModel):
    cart: CartResponse
    migrated_items_count: int
    warnings: list[str] = Field(default_factory=list)
