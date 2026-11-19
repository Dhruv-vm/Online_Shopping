import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ================= Profile & Overview Schemas =================


class RetailerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    rating: float
    state: str | None
    business_address: str | None
    contact_phone: str | None
    contact_email: str | None
    business_hours: dict[str, Any] | None
    policies: dict[str, Any] | None
    is_open: bool
    verification_status: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime | None = None


class RetailerProfileUpdateRequest(BaseModel):
    description: str | None = Field(None, max_length=2000)
    logo_url: str | None = Field(None, max_length=1024)
    business_address: str | None = Field(None, max_length=1000)
    contact_phone: str | None = Field(None, max_length=15)
    contact_email: str | None = Field(None, max_length=255)
    business_hours: dict[str, Any] | None = None
    policies: dict[str, Any] | None = None
    is_open: bool | None = None


class RetailerOverviewResponse(BaseModel):
    retailer_id: uuid.UUID
    store_name: str
    slug: str
    state: str | None
    is_open: bool
    verification_status: str
    rating: float
    total_listings: int
    active_listings: int
    total_inventory_units: int
    low_stock_alerts: int
    out_of_stock_alerts: int
    recent_orders_count: int


# ================= Catalogue Lookup for Retailer =================


class CatalogueVariantItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku: str
    attributes: dict[str, Any]
    is_active: bool
    is_already_listed: bool = False
    existing_listing_id: uuid.UUID | None = None


class CatalogueProductLookupItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    brand: str
    category_id: uuid.UUID
    category_name: str
    description: str | None
    image_url: str | None
    variants: list[CatalogueVariantItem]


# ================= Listing Schemas =================


class ListingInventorySummary(BaseModel):
    on_hand_quantity: int
    reserved_quantity: int
    available_quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    is_out_of_stock: bool


class RetailerListingResponse(BaseModel):
    id: uuid.UUID
    retailer_id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    brand: str
    category_name: str
    variant_name: str
    variant_sku: str
    variant_attributes: dict[str, Any]
    seller_sku: str | None
    original_price_paise: int
    selling_price_paise: int
    currency: str
    hsn_code: str | None
    gst_rate_basis_points: int | None
    is_tax_verified: bool
    is_active: bool
    image_url: str | None
    inventory: ListingInventorySummary
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RetailerListingCreateRequest(BaseModel):
    variant_id: uuid.UUID
    seller_sku: str | None = Field(None, max_length=100)
    original_price_paise: int = Field(
        ..., ge=0, description="Maximum Retail Price (MRP) in paise"
    )
    selling_price_paise: int = Field(..., ge=0, description="Selling price in paise")
    hsn_code: str | None = Field(None, max_length=16)
    gst_rate_basis_points: int | None = Field(default=1800, ge=0, le=10000)
    is_active: bool = True
    initial_on_hand_quantity: int = Field(
        default=0, ge=0, description="Initial stock level"
    )
    low_stock_threshold: int = Field(
        default=10, ge=0, description="Alert threshold for low stock"
    )

    @model_validator(mode="after")
    def validate_pricing_hierarchy(self) -> "RetailerListingCreateRequest":
        if self.selling_price_paise > self.original_price_paise:
            raise ValueError("Selling price cannot exceed the original MRP price.")
        return self


class RetailerListingUpdateRequest(BaseModel):
    seller_sku: str | None = Field(None, max_length=100)
    original_price_paise: int | None = Field(None, ge=0)
    selling_price_paise: int | None = Field(None, ge=0)
    hsn_code: str | None = Field(None, max_length=16)
    gst_rate_basis_points: int | None = Field(None, ge=0, le=10000)
    is_active: bool | None = None
    low_stock_threshold: int | None = Field(None, ge=0)


class RetailerListingListResponse(BaseModel):
    items: list[RetailerListingResponse]
    total: int
    limit: int
    offset: int


# ================= Inventory Schemas =================


class RetailerInventoryItemResponse(BaseModel):
    listing_id: uuid.UUID
    product_name: str
    variant_name: str
    sku: str
    seller_sku: str | None
    selling_price_paise: int
    on_hand_quantity: int
    reserved_quantity: int
    available_quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    is_out_of_stock: bool
    is_active: bool
    updated_at: datetime.datetime


class InventorySummaryStats(BaseModel):
    total_items: int
    total_on_hand_units: int
    total_reserved_units: int
    total_available_units: int
    low_stock_count: int
    out_of_stock_count: int


class RetailerInventoryDashboardResponse(BaseModel):
    summary: InventorySummaryStats
    items: list[RetailerInventoryItemResponse]
    total: int
    limit: int
    offset: int


class RetailerInventoryAdjustmentRequest(BaseModel):
    adjustment_type: Literal["SET", "DELTA"]
    quantity: int = Field(
        ...,
        description="Absolute count if SET (must be >= 0), or positive/negative change if DELTA",
    )
    low_stock_threshold: int | None = Field(None, ge=0)
    reason: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_set_non_negative(self) -> "RetailerInventoryAdjustmentRequest":
        if self.adjustment_type == "SET" and self.quantity < 0:
            raise ValueError(
                "Quantity cannot be negative when adjustment_type is 'SET'."
            )
        return self


class RetailerBulkInventoryAdjustmentItem(BaseModel):
    listing_id: uuid.UUID
    on_hand_quantity: int = Field(..., ge=0)
    low_stock_threshold: int | None = Field(None, ge=0)


class RetailerBulkInventoryAdjustmentRequest(BaseModel):
    items: list[RetailerBulkInventoryAdjustmentItem] = Field(
        ..., min_length=1, max_length=100
    )
