import datetime
import uuid

from pydantic import BaseModel


class SaleStreamItem(BaseModel):
    id: uuid.UUID
    event_type: str
    listing_id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    variant_name: str
    image_url: str | None
    retailer_id: uuid.UUID
    retailer_name: str
    category_slug: str | None
    old_price_paise: int
    deal_price_paise: int
    current_price_paise: int
    discount_pct: float
    stock_remaining: int
    units_sold_24h: int | None
    starts_at: datetime.datetime
    expires_at: datetime.datetime
    seconds_remaining: int
    created_at: datetime.datetime


class SaleStreamResponse(BaseModel):
    items: list[SaleStreamItem]
    next_cursor: datetime.datetime | None
    server_time: datetime.datetime
    poll_after_seconds: int = 15
