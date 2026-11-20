import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.pincode import validate_pincode


class DemandSignalRequest(BaseModel):
    query_text: str | None = Field(None, min_length=2, max_length=200)
    listing_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    pincode: str | None = None
    signal_type: Literal["OUT_OF_STOCK", "WISHLIST"] = "WISHLIST"

    @field_validator("pincode")
    @classmethod
    def _pin(cls, v: str | None) -> str | None:
        return validate_pincode(v)

    @model_validator(mode="after")
    def _need_subject(self):
        if not self.query_text and not self.listing_id:
            raise ValueError("Provide query_text or listing_id")
        if self.signal_type == "OUT_OF_STOCK" and not self.listing_id:
            raise ValueError("OUT_OF_STOCK signals require listing_id")
        return self


class DemandJoinRequest(BaseModel):
    pincode: str | None = None

    @field_validator("pincode")
    @classmethod
    def _pin(cls, v: str | None) -> str | None:
        return validate_pincode(v)


class DemandPoolOffer(BaseModel):
    retailer_id: uuid.UUID
    retailer_name: str
    listing_id: uuid.UUID
    offered_price_paise: int
    note: str | None
    created_at: datetime.datetime


class DemandPoolItem(BaseModel):
    id: uuid.UUID
    display_name: str
    normalized_product_name: str
    category_id: uuid.UUID | None
    pincode: str | None
    total_demand_count: int
    unique_users_count: int
    visibility_threshold: int
    status: str
    last_signal_at: datetime.datetime
    fulfilled_at: datetime.datetime | None
    created_at: datetime.datetime
    offers: list[DemandPoolOffer] = Field(default_factory=list)
    responded_by_me: bool | None = None


class DemandSignalResponse(BaseModel):
    pool: DemandPoolItem
    deduplicated: bool


class DemandPoolListResponse(BaseModel):
    items: list[DemandPoolItem]
    total: int


class DemandFulfillRequest(BaseModel):
    listing_id: uuid.UUID
    note: str | None = Field(None, max_length=500)


class AdminDemandPoolUpdate(BaseModel):
    status: Literal["OPEN", "FULFILLED", "EXPIRED"] | None = None
    visibility_threshold: int | None = Field(None, ge=1, le=10000)


class DemandTrendPoint(BaseModel):
    date: datetime.date
    signals: int


class DemandTrendsResponse(BaseModel):
    daily: list[DemandTrendPoint]
    top_pools: list[DemandPoolItem]
