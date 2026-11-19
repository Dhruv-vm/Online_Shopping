import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class AdminOverviewResponse(BaseModel):
    total_orders: int
    total_revenue_paise: int
    total_customers: int
    total_retailers: int
    pending_verifications: int
    active_products: int


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
    created_at: datetime.datetime


class RetailerVerifyRequest(BaseModel):
    status: str = Field(..., pattern="^(VERIFIED|REJECTED|SUSPENDED)$")
    rejection_reason: str | None = None
