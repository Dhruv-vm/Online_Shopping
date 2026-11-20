from __future__ import annotations

import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
