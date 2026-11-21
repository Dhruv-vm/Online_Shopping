from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ShoppingPriority(StrEnum):
    LOWEST_PRICE = "LOWEST_PRICE"
    QUALITY = "QUALITY"
    DURABILITY = "DURABILITY"
    CONVENIENCE = "CONVENIENCE"
    BALANCED = "BALANCED"


class Frequency(StrEnum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEASONAL = "SEASONAL"
    CUSTOM = "CUSTOM"


class MemoryType(StrEnum):
    PREFERENCE = "PREFERENCE"
    RECURRING_GOAL = "RECURRING_GOAL"
    NOTE = "NOTE"
    CONTEXT = "CONTEXT"


class MemorySource(StrEnum):
    CUSTOMER_STATED = "CUSTOMER_STATED"
    MISSION_DERIVED = "MISSION_DERIVED"
    SYSTEM_SUGGESTED = "SYSTEM_SUGGESTED"


class CustomerPreferenceProfileRequest(BaseModel):
    preferred_brands: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_retailers: list[str] = Field(default_factory=list)
    preferred_price_range: dict[str, Any] = Field(default_factory=dict)
    preferred_attributes: dict[str, Any] = Field(default_factory=dict)
    shopping_priorities: list[str] = Field(default_factory=list)
    category_preferences: dict[str, Any] = Field(default_factory=dict)
    personalization_enabled: bool | None = None


class CustomerPreferenceProfileResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    preferred_brands: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_retailers: list[str] = Field(default_factory=list)
    preferred_price_range: dict[str, Any] = Field(default_factory=dict)
    preferred_attributes: dict[str, Any] = Field(default_factory=dict)
    shopping_priorities: list[str] = Field(default_factory=list)
    category_preferences: dict[str, Any] = Field(default_factory=dict)
    personalization_enabled: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PersonalizationConsentRequest(BaseModel):
    personalization_enabled: bool


class PersonalizationConsentResponse(BaseModel):
    personalization_enabled: bool
    updated_at: datetime.datetime
    message: str


class RecurringIntentionCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    category_ids: list[str] = Field(default_factory=list)
    frequency: str = Field(default="MONTHLY", max_length=32)
    budget_paise: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class RecurringIntentionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    category_ids: list[str] | None = None
    frequency: str | None = Field(default=None, max_length=32)
    budget_paise: int | None = Field(default=None, ge=0)
    notes: str | None = None
    is_active: bool | None = None


class RecurringIntentionStatusRequest(BaseModel):
    is_active: bool


class RecurringIntentionResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    title: str
    category_ids: list[str] = Field(default_factory=list)
    frequency: str
    budget_paise: int | None = None
    notes: str | None = None
    is_active: bool
    last_executed_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class IntentMemoryItemCreateRequest(BaseModel):
    memory_type: str = Field(default="PREFERENCE", max_length=64)
    key: str = Field(..., min_length=1, max_length=128)
    value: dict[str, Any] | str = Field(default_factory=dict)
    summary: str = Field(..., min_length=2, max_length=255)
    source: str = Field(default="CUSTOMER_STATED", max_length=32)


class IntentMemoryItemResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    memory_type: str
    key: str
    value: dict[str, Any] | str
    summary: str
    source: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class IntentOverviewResponse(BaseModel):
    profile: CustomerPreferenceProfileResponse | None = None
    recurring_intentions: list[RecurringIntentionResponse] = Field(default_factory=list)
    memories: list[IntentMemoryItemResponse] = Field(default_factory=list)
    active_intentions_count: int = 0
    total_memories_count: int = 0
    personalization_enabled: bool = False


class IntentSuggestionResponse(BaseModel):
    suggested_brands: list[str] = Field(default_factory=list)
    suggested_priorities: list[str] = Field(default_factory=list)
    suggested_budget_paise: int | None = None
    suggested_categories: list[str] = Field(default_factory=list)
    applicable_intentions: list[RecurringIntentionResponse] = Field(
        default_factory=list
    )
    personalization_enabled: bool = False
    explanation: str | None = None


# ---------------------------------------------------------------- intent workflow
class IntentItemIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    quantity: int = Field(default=1, ge=1, le=50)
    specs: str | None = Field(default=None, max_length=300)


class IntentSubmitRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    items: list[IntentItemIn] = Field(..., min_length=1, max_length=20)
    budget_paise: int | None = Field(default=None, ge=0)
    frequency: str = Field(default="ONCE", max_length=32)
    pincode: str | None = None
    purchase_by: datetime.date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("pincode")
    @classmethod
    def _pin(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not (len(v) == 6 and v.isdigit() and v[0] != "0"):
            raise ValueError("Enter a valid 6-digit PIN code.")
        return v

    @field_validator("frequency")
    @classmethod
    def _freq(cls, v: str) -> str:
        v = (v or "ONCE").upper()
        allowed = {
            "ONCE",
            "WEEKLY",
            "BIWEEKLY",
            "MONTHLY",
            "QUARTERLY",
            "SEASONAL",
            "CUSTOM",
        }
        if v not in allowed:
            raise ValueError(f"frequency must be one of {sorted(allowed)}")
        return v


class IntentListingMatch(BaseModel):
    listing_id: uuid.UUID
    product_name: str
    product_slug: str
    variant_name: str
    retailer_name: str
    price_paise: int
    original_price_paise: int
    available_quantity: int
    offers: list[str] = Field(default_factory=list)


class IntentDemandStatus(BaseModel):
    pool_id: uuid.UUID
    display_name: str
    unique_customers: int
    visibility_threshold: int
    visible_to_retailers: bool
    status: str
    signal_recorded_now: bool


class IntentItemResult(BaseModel):
    name: str
    quantity: int
    specs: str | None = None
    understood_as: str
    category: str | None = None
    status: str  # AVAILABLE | NOT_AVAILABLE
    matches: list[IntentListingMatch] = Field(default_factory=list)
    retailer_count: int = 0
    demand: IntentDemandStatus | None = None
    next_step: str


class IntentWorkflowResponse(BaseModel):
    intention: RecurringIntentionResponse
    items_requested: list[IntentItemIn]
    pincode: str | None = None
    purchase_by: datetime.date | None = None
    updated_existing: bool = False
    status: str  # MATCHED | PARTIALLY_MATCHED | WAITING_FOR_SUPPLY
    items: list[IntentItemResult]
    cheapest_total_paise: int = 0
    within_budget: bool | None = None
    can_create_basket: bool = False
    next_steps: list[str] = Field(default_factory=list)
    analyzed_at: datetime.datetime


class IntentBasketResponse(BaseModel):
    added: list[dict]
    skipped: list[str]
    message: str


class IntentSummary(BaseModel):
    id: uuid.UUID
    title: str
    frequency: str
    budget_paise: int | None = None
    pincode: str | None = None
    item_count: int
    is_active: bool
    last_status: str | None = None
    analyzed_at: datetime.datetime | None = None
