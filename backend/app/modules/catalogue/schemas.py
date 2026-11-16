import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CategorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    image_url: str | None = None
    icon: str | None = None
    parent_id: uuid.UUID | None = None
    product_count: int = 0


class RetailerSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    rating: float = 5.0
    is_active: bool = True


class ProductImageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    alt_text: str | None = None
    is_primary: bool = False
    sort_order: int = 0
    variant_id: uuid.UUID | None = None


class ProductListingDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_rating: float
    seller_sku: str | None = None
    original_price_paise: int
    selling_price_paise: int
    currency: str = "INR"
    is_active: bool = True
    on_hand_quantity: int = 0
    reserved_quantity: int = 0
    available_quantity: int = 0
    is_in_stock: bool = False


class ProductVariantDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    sku: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    listings: list[ProductListingDetailSchema] = Field(default_factory=list)
    min_price_paise: int | None = None
    is_in_stock: bool = False


class ProductSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand: str
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    primary_image: str | None = None
    min_price_paise: int
    max_price_paise: int
    original_price_paise: int | None = None
    currency: str = "INR"
    is_in_stock: bool
    variant_count: int
    retailer_count: int


class ProductListResponseSchema(BaseModel):
    items: list[ProductSummarySchema]
    total: int
    page: int
    limit: int
    pages: int


class ProductDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    brand: str
    description: str | None = None
    category_id: uuid.UUID
    category_name: str
    category_slug: str
    images: list[ProductImageSchema] = Field(default_factory=list)
    variants: list[ProductVariantDetailSchema] = Field(default_factory=list)
    min_price_paise: int
    max_price_paise: int
    original_price_paise: int | None = None
    currency: str = "INR"
    is_in_stock: bool
    total_available_stock: int
