from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class SearchFacetBucket(BaseModel):
    """Aggregation bucket for faceted navigation."""

    key: str
    doc_count: int


class SearchFacets(BaseModel):
    """Categorical aggregations for search refinement."""

    categories: list[SearchFacetBucket] = Field(default_factory=list)
    brands: list[SearchFacetBucket] = Field(default_factory=list)
    retailers: list[SearchFacetBucket] = Field(default_factory=list)
    price_stats: dict[str, Any] = Field(default_factory=dict)


class ProductSearchItem(BaseModel):
    """Product document representation returned by search APIs."""

    product_id: uuid.UUID | str
    name: str
    slug: str
    brand: str
    description: str = ""
    category_id: str = ""
    category_name: str = ""
    category_slug: str = ""
    primary_image_url: str | None = None
    min_price_paise: int = 0
    max_price_paise: int = 0
    currency: str = "INR"
    is_in_stock: bool = True
    total_available_quantity: int = 0
    rating: float = 5.0
    retailers: list[dict[str, Any]] = Field(default_factory=list)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    attributes: dict[str, list[str]] = Field(default_factory=dict)


class SearchResponseSchema(BaseModel):
    """Universal search response payload."""

    items: list[ProductSearchItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 1
    engine: Literal["opensearch", "postgres_fallback"] = "opensearch"
    facets: SearchFacets | None = None
    took_ms: float = 0.0


class SuggestionItem(BaseModel):
    """Auto-completion / suggestion entry."""

    text: str
    type: Literal["product", "brand", "category"] = "product"
    slug: str | None = None


class SuggestionsResponse(BaseModel):
    """Suggestions / type-ahead payload."""

    query: str
    suggestions: list[SuggestionItem] = Field(default_factory=list)
