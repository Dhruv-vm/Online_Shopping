import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    date: datetime.date
    price_paise: int
    day_low_paise: int
    mrp_paise: int
    source: Literal["LIVE", "DEMO_SEED"] = "LIVE"


class PriceIntelligenceResponse(BaseModel):
    listing_id: uuid.UUID
    currency: str
    window_days: int
    current_price_paise: int
    current_mrp_paise: int
    lowest_price_paise: int
    highest_price_paise: int
    average_price_30d_paise: int | None
    average_price_90d_paise: int | None
    current_vs_30d_average_pct: float | None
    discount_from_mrp_pct: float
    is_lowest_in_window: bool
    days_of_history: int
    badge: Literal[
        "GENUINE_DISCOUNT",
        "MRP_INFLATED",
        "NO_SPECIAL_DISCOUNT",
        "INSUFFICIENT_HISTORY",
    ]
    badge_reason: str
    history: list[PricePoint]
    contains_demo_data: bool = False
    demo_days: int = 0
    demo_data_notice: str | None = None


class PriceComparisonOffer(BaseModel):
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    retailer_state: str | None
    selling_price_paise: int
    mrp_paise: int
    discount_from_mrp_pct: float
    available_quantity: int
    in_stock: bool
    is_cheapest: bool
    difference_from_cheapest_paise: int


class PriceComparisonResponse(BaseModel):
    variant_id: uuid.UUID
    product_name: str
    variant_name: str
    offers: list[PriceComparisonOffer]
    cheapest_price_paise: int | None
    price_spread_paise: int
    explanation: str


class PriceAlertCreateRequest(BaseModel):
    variant_id: uuid.UUID
    target_price_paise: int = Field(..., gt=0)


class PriceAlertItem(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    product_name: str
    variant_name: str
    target_price_paise: int
    current_best_price_paise: int | None
    status: str
    triggered_price_paise: int | None
    triggered_at: datetime.datetime | None
    created_at: datetime.datetime


class RetailerPriceInsight(BaseModel):
    listing_id: uuid.UUID
    product_name: str
    variant_name: str
    my_price_paise: int
    competitor_count: int
    lowest_competitor_price_paise: int | None
    my_rank: int
    gap_to_lowest_paise: int | None
    days_of_history: int
    active_price_alerts: int


class PriceDataQualityResponse(BaseModel):
    active_listings: int
    listings_without_history: int
    listings_with_demo_history: int
    live_ticks: int
    demo_ticks: int
    stale_listings_7d: int
    selling_above_mrp: int
    large_daily_swings: int
    active_price_alerts: int
    generated_at: datetime.datetime
