import datetime
import uuid

from pydantic import BaseModel, Field, field_validator

from app.core.pincode import validate_pincode


class ManifestItem(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    quantity: int = Field(..., ge=1, le=10)
    unit: str | None = Field(None, max_length=32)
    notes: str | None = Field(None, max_length=300)


class ExchangeRequestCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=160)
    delivery_pincode: str
    budget_limit_paise: int | None = Field(None, gt=0)
    items: list[ManifestItem] = Field(..., min_length=1, max_length=20)
    bidding_hours: int = Field(48, ge=1, le=168)

    @field_validator("delivery_pincode")
    @classmethod
    def _pin(cls, v: str) -> str:
        out = validate_pincode(v)
        if not out:
            raise ValueError("delivery_pincode is required")
        return out


class BidLineInput(BaseModel):
    manifest_index: int = Field(..., ge=0, le=19)
    listing_id: uuid.UUID
    unit_price_paise: int = Field(..., gt=0)


class BidSubmitRequest(BaseModel):
    lines: list[BidLineInput] = Field(..., min_length=1, max_length=20)
    estimated_delivery_hours: int = Field(..., ge=1, le=336)
    notes: str | None = Field(None, max_length=1000)


class AcceptBidRequest(BaseModel):
    bid_id: uuid.UUID


class BidLine(BaseModel):
    manifest_index: int
    item_name: str
    listing_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price_paise: int
    list_price_paise: int
    line_total_paise: int


class BidItem(BaseModel):
    id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_rating: float
    bid_amount_paise: int
    estimated_delivery_hours: int
    items_covered: int
    items_requested: int
    notes: str | None
    status: str
    lines: list[BidLine]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ExchangeRequestItem(BaseModel):
    id: uuid.UUID
    title: str
    delivery_pincode: str
    budget_limit_paise: int | None
    items: list[ManifestItem]
    status: str
    accepted_bid_id: uuid.UUID | None
    expires_at: datetime.datetime
    created_at: datetime.datetime
    bid_count: int
    bids: list[BidItem] | None = None
    my_bid: BidItem | None = None


class ExchangeRequestList(BaseModel):
    items: list[ExchangeRequestItem]
    total: int


class AcceptBidResponse(BaseModel):
    request: ExchangeRequestItem
    cart_id: uuid.UUID
    awarded_lines: int
    message: str
