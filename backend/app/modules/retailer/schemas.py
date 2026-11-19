import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    total_inventory_units: int
    recent_orders_count: int
