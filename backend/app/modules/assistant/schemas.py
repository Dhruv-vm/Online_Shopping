import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)


class AssistantSeller(BaseModel):
    listing_id: uuid.UUID
    retailer_id: uuid.UUID | None
    retailer_name: str
    price_paise: int
    mrp_paise: int
    available_quantity: int
    negotiable: bool


class AssistantOption(BaseModel):
    product_id: uuid.UUID
    name: str
    brand: str
    category_slug: str
    image_url: str | None
    best_price_paise: int
    sellers: list[AssistantSeller]
    within_budget: bool
    explanation: str


class AssistantReply(BaseModel):
    mode: Literal["rule_based"]
    ai_provider_configured: bool
    understood: dict[str, Any]
    message: str
    options: list[AssistantOption]
    alternatives: list[AssistantOption]
    disclaimer: str
