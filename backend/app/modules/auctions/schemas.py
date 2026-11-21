import datetime
import uuid

from pydantic import BaseModel, Field, field_validator

from app.core.pincode import validate_pincode


class AuctionStartRequest(BaseModel):
    pincode: str

    @field_validator("pincode")
    @classmethod
    def _pin(cls, v: str) -> str:
        out = validate_pincode(v)
        if not out:
            raise ValueError("pincode is required")
        return out


class AuctionBidRequest(BaseModel):
    bid_price_paise: int = Field(..., gt=0)
    delivery_eta_minutes: int = Field(..., ge=10, le=1440)
    warranty_note: str | None = Field(None, max_length=300)


class AuctionAcceptRequest(BaseModel):
    bid_id: uuid.UUID


class SnapshotItem(BaseModel):
    variant_id: uuid.UUID
    product_name: str
    variant_name: str
    quantity: int
    reference_unit_price_paise: int


class AuctionBidView(BaseModel):
    id: uuid.UUID
    rank: int
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_rating: float
    bid_price_paise: int
    savings_paise: int
    delivery_eta_minutes: int
    warranty_note: str | None
    is_simulated: bool = False
    created_at: datetime.datetime


class BidLadderEntry(BaseModel):
    """One bid as other stores may see it: price and time only, never the store."""

    price_paise: int
    at: datetime.datetime
    mine: bool


class AuctionView(BaseModel):
    id: uuid.UUID
    status: str
    pincode: str
    items: list[SnapshotItem]
    reference_total_paise: int
    duration_seconds: int
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    seconds_remaining: int
    bid_count: int
    best_bid_paise: int | None
    winning_bid_id: uuid.UUID | None
    bids: list[AuctionBidView] | None = None
    my_best_bid_paise: int | None = None
    my_list_total_paise: int | None = None
    # Retailer view only (Dukaan vs Dukaan):
    my_rank: int | None = None
    competing_stores: int | None = None
    is_winning: bool | None = None
    outbid: bool | None = None
    bid_ladder: list[BidLadderEntry] | None = None
    # WON | NOT_SELECTED | AWAITING_CHOICE | CLOSED (only once bidding has ended)
    my_outcome: str | None = None


class AuctionList(BaseModel):
    items: list[AuctionView]
    total: int


class AuctionAcceptResponse(BaseModel):
    auction: AuctionView
    cart_id: uuid.UUID
    message: str
