import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.cart.schemas import CartResponse


class SubstituteType(StrEnum):
    CLOSEST_MATCH = "CLOSEST_MATCH"
    BUDGET_FRIENDLY = "BUDGET_FRIENDLY"
    BETTER_VALUE = "BETTER_VALUE"
    PREMIUM_UPGRADE = "PREMIUM_UPGRADE"
    AVAILABLE_NOW = "AVAILABLE_NOW"


class AvailabilityStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"


class SpecComparison(BaseModel):
    attribute_key: str
    label: str
    original_value: Any
    substitute_value: Any
    is_match: bool


class SubstituteItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    listing_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_slug: str
    brand: str
    variant_id: uuid.UUID
    variant_name: str
    variant_sku: str
    variant_attributes: dict[str, Any] = Field(default_factory=dict)
    primary_image_url: str | None = None
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_slug: str
    retailer_rating: float
    retailer_verification_status: str
    original_price_paise: int
    selling_price_paise: int
    price_diff_paise: (
        int  # substitute selling price - original selling price (negative = savings)
    )
    price_diff_percentage: float  # (selling - original) / original * 100
    savings_percentage: float  # positive percentage saved, 0.0 if not cheaper
    available_stock: int
    is_in_stock: bool
    availability_status: AvailabilityStatus
    similarity_score: float  # 0.0 to 1.0
    substitute_type: SubstituteType
    applicable_types: list[SubstituteType] = Field(default_factory=list)
    reason: str
    matching_specs: list[str] = Field(default_factory=list)
    differing_specs: list[str] = Field(default_factory=list)
    detailed_comparisons: list[SpecComparison] = Field(default_factory=list)
    compatibility_notes: str | None = None


class SubstituteListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    original_listing_id: uuid.UUID
    original_product_name: str
    original_product_slug: str
    original_brand: str
    original_category_id: uuid.UUID
    original_category_name: str
    original_selling_price_paise: int
    original_is_in_stock: bool
    original_available_stock: int
    original_attributes: dict[str, Any] = Field(default_factory=dict)
    substitutes: list[SubstituteItemResponse] = Field(default_factory=list)
    total_count: int
    trigger_reason: str | None = None


class CartItemReplaceRequest(BaseModel):
    new_listing_id: uuid.UUID
    quantity: int | None = Field(None, ge=1, le=10)


class CartItemReplaceResponse(BaseModel):
    cart: CartResponse
    replaced_item_id: uuid.UUID
    new_item_id: uuid.UUID
    message: str
