import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.validation import validate_media_url


class AdminOverviewResponse(BaseModel):
    """Platform KPIs. Quarantined automated-test records are excluded.

    * total_orders: all orders by real customers (any status).
    * paid_orders / total_revenue_paise: orders with captured payment and
      their payable total (gross, before refunds).
    * refunded_paise: refunds issued on those orders.
    * total_customers: active customer accounts.
    * total_retailers: stores excluding quarantined test fixtures.
    """

    total_orders: int
    total_revenue_paise: int
    total_customers: int
    total_retailers: int
    pending_verifications: int
    active_products: int
    paid_orders: int = 0
    pending_payment_orders: int = 0
    refunded_paise: int = 0
    active_retailers: int = 0
    excluded_test_records: int = 0


class AdminRetailerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    state: str | None
    verification_status: str
    is_active: bool
    is_open: bool
    business_address: str | None
    contact_phone: str | None
    contact_email: str | None
    owner_name: str | None = None
    owner_email: str | None = None
    documents_count: int = 0
    created_at: datetime.datetime


class RetailerDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_type: str
    document_url: str
    document_number: str | None = None
    has_private_file: bool = False
    status: str
    rejection_reason: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RetailerVerificationHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    from_status: str
    to_status: str
    reason: str | None = None
    admin_id: uuid.UUID | None = None
    created_at: datetime.datetime


class AdminRetailerDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    state: str | None
    verification_status: str
    is_active: bool
    is_open: bool
    business_address: str | None
    contact_phone: str | None
    contact_email: str | None
    description: str | None = None
    logo_url: str | None = None
    rating: float
    owner_name: str | None = None
    owner_email: str | None = None
    reviewed_by_user_id: uuid.UUID | None = None
    verified_at: datetime.datetime | None = None
    rejection_reason: str | None = None
    created_at: datetime.datetime
    documents: list[RetailerDocumentItem] = Field(default_factory=list)
    verification_history: list[RetailerVerificationHistoryItem] = Field(
        default_factory=list
    )


class RetailerVerifyRequest(BaseModel):
    status: str = Field(..., pattern="^(VERIFIED|REJECTED|SUSPENDED)$")
    rejection_reason: str | None = None


class DocumentVerifyRequest(BaseModel):
    status: str = Field(..., pattern="^(VERIFIED|REJECTED)$")
    rejection_reason: str | None = None


# ================= Catalogue Schemas =================


class AdminCatalogueVariantItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    sku: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime.datetime
    listings_count: int = 0


class AdminCatalogueProductListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand: str
    category_id: uuid.UUID
    category_name: str | None = None
    is_active: bool
    variants_count: int = 0
    listings_count: int = 0
    primary_image_url: str | None = None
    created_at: datetime.datetime


class AdminCatalogueProductDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand: str
    category_id: uuid.UUID
    category_name: str | None = None
    description: str | None = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    images: list[dict[str, Any]] = Field(default_factory=list)
    variants: list[AdminCatalogueVariantItem] = Field(default_factory=list)
    active_listings_count: int = 0


class AdminCatalogueVariantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    sku: str = Field(..., min_length=3, max_length=100)
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class AdminCatalogueVariantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    sku: str | None = Field(default=None, min_length=3, max_length=100)
    attributes: dict[str, Any] | None = None
    is_active: bool | None = None


class AdminCatalogueProductCreateRequest(BaseModel):
    category_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    brand: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True
    image_urls: list[str] = Field(default_factory=list, max_length=20)
    variants: list[AdminCatalogueVariantCreateRequest] = Field(default_factory=list)

    @field_validator("image_urls")
    @classmethod
    def _validate_image_urls(cls, v: list[str]) -> list[str]:
        return [u for u in (validate_media_url(x) for x in v) if u]


class AdminCatalogueProductUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class AdminCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    parent_id: uuid.UUID | None = None
    is_active: bool = True

    @field_validator("image_url")
    @classmethod
    def _validate_image_url(cls, v: str | None) -> str | None:
        return validate_media_url(v)


class AdminCategoryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    parent_id: uuid.UUID | None = None
    parent_name: str | None = None
    is_active: bool
    product_count: int = 0
    children: list["AdminCategoryListItem"] = Field(default_factory=list)


# ================= Deals & Promotions Schemas =================


class AdminDealListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str | None = None
    discount_type: str
    discount_value: int
    scope: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    listing_id: uuid.UUID | None = None
    min_order_paise: int
    max_discount_paise: int | None = None
    usage_limit: int | None = None
    times_used: int
    is_active: bool
    valid_from: datetime.datetime
    valid_to: datetime.datetime | None = None
    status: str  # ACTIVE, SCHEDULED, EXPIRED, PAUSED
    created_at: datetime.datetime


class AdminDealDetailResponse(AdminDealListItem):
    description: str | None = None
    updated_at: datetime.datetime


class AdminDealCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    discount_type: str = Field(..., pattern="^(PERCENTAGE|FIXED_AMOUNT)$")
    # If PERCENTAGE: basis points (e.g. 1000 = 10%, max 9000 = 90%)
    # If FIXED_AMOUNT: paise (e.g. 5000 = ₹50)
    discount_value: int = Field(..., gt=0)
    scope: str = Field(
        default="PLATFORM_WIDE",
        pattern="^(PLATFORM_WIDE|CATEGORY|PRODUCT|LISTING)$",
    )
    category_id: uuid.UUID | None = None
    product_id: uuid.UUID | None = None
    listing_id: uuid.UUID | None = None
    min_order_paise: int = Field(default=0, ge=0)
    max_discount_paise: int | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    valid_from: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    valid_to: datetime.datetime | None = None
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_deal_rules(self) -> "AdminDealCreateRequest":
        if self.discount_type == "PERCENTAGE" and self.discount_value > 9000:
            raise ValueError(
                "Percentage discount value cannot exceed 9000 basis points (90%)."
            )
        if self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError(
                "Deal valid_to timestamp must be strictly after valid_from."
            )
        if self.scope == "CATEGORY" and not self.category_id:
            raise ValueError("category_id is required when deal scope is CATEGORY.")
        if self.scope == "PRODUCT" and not self.product_id:
            raise ValueError("product_id is required when deal scope is PRODUCT.")
        if self.scope == "LISTING" and not self.listing_id:
            raise ValueError("listing_id is required when deal scope is LISTING.")
        return self


class AdminDealUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=255)
    code: str | None = Field(default=None, max_length=50)
    discount_type: str | None = Field(
        default=None, pattern="^(PERCENTAGE|FIXED_AMOUNT)$"
    )
    discount_value: int | None = Field(default=None, gt=0)
    min_order_paise: int | None = Field(default=None, ge=0)
    max_discount_paise: int | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, gt=0)
    valid_from: datetime.datetime | None = None
    valid_to: datetime.datetime | None = None
    description: str | None = None
    is_active: bool | None = None


# ================= Retailer Sales Analytics =================


class AdminRetailerSalesProductItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: uuid.UUID
    product_name: str
    variant_id: uuid.UUID
    variant_name: str
    sku: str | None = None
    quantity_sold: int
    selling_price_paise: int
    gross_revenue_paise: int
    refund_quantity: int = 0
    refund_amount_paise: int = 0
    net_sales_paise: int


class AdminRetailerSalesAnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retailer_id: uuid.UUID
    retailer_name: str
    state: str | None = None
    verification_status: str
    is_active: bool
    total_orders: int
    total_units_sold: int
    gross_merchandise_value_paise: int
    refunded_amount_paise: int
    net_sales_paise: int
    currency: str = "INR"
    product_sales: list[AdminRetailerSalesProductItem] = Field(default_factory=list)
