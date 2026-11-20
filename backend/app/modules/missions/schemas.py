import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MissionCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str | None = Field(None, max_length=2000)
    budget_paise: int = Field(
        ..., gt=0, description="Total budget in paise (e.g. 1500000 = Rs 15,000)"
    )
    category_id: uuid.UUID | None = None
    people_count: int = Field(1, ge=1, le=50)
    preferences: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)


class MissionUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=255)
    description: str | None = Field(None, max_length=2000)
    budget_paise: int | None = Field(None, gt=0)
    status: str | None = Field(None, pattern="^(ACTIVE|SAVED|COMPLETED|ARCHIVED)$")
    people_count: int | None = Field(None, ge=1, le=50)
    preferences: list[str] | None = None
    excluded_brands: list[str] | None = None


class MissionItemUpdateRequest(BaseModel):
    quantity: int | None = Field(None, ge=1, le=999)
    is_selected: bool | None = None
    group_name: str | None = Field(None, max_length=100)


class MissionItemAddRequest(BaseModel):
    listing_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=999)
    group_name: str = Field("Additional Items", max_length=100)


class MissionItemReplaceRequest(BaseModel):
    new_listing_id: uuid.UUID
    quantity: int | None = Field(None, ge=1, le=999)


class MissionAlternativeItemResponse(BaseModel):
    listing_id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    brand: str
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_slug: str
    selling_price_paise: int
    price_diff_paise: int
    available_stock: int
    is_in_stock: bool
    image_url: str | None = None
    match_type: str = "CATEGORY_MATCH"

    model_config = ConfigDict(from_attributes=True)


class MissionItemResponse(BaseModel):
    id: uuid.UUID
    mission_id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    product_name: str
    brand: str
    variant_name: str
    sku: str
    retailer_name: str
    retailer_slug: str
    image_url: str | None = None
    group_name: str
    quantity: int
    unit_price_paise: int
    current_selling_price_paise: int
    price_changed: bool
    available_stock: int
    is_in_stock: bool
    subtotal_paise: int
    is_selected: bool
    recommendation_reason: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class MissionGroupResponse(BaseModel):
    group_name: str
    items: list[MissionItemResponse]
    subtotal_paise: int
    items_count: int


class MissionSummaryResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    budget_paise: int
    total_cost_paise: int
    remaining_budget_paise: int
    is_over_budget: bool
    items_count: int
    status: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    people_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MissionDetailResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    title: str
    description: str | None = None
    budget_paise: int
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    people_count: int
    preferences: list[str]
    excluded_brands: list[str]
    status: str
    total_cost_paise: int
    remaining_budget_paise: int
    is_over_budget: bool
    budget_shortfall_paise: int
    items_count: int
    unavailable_items_count: int
    summary_explanation: str
    groups: list[MissionGroupResponse]
    items: list[MissionItemResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MissionAddToCartResponse(BaseModel):
    mission_id: uuid.UUID
    added_items_count: int
    skipped_items_count: int
    warnings: list[str]
    cart: dict[str, Any]
