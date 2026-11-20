import datetime
import uuid
from typing import Literal

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: datetime.date
    price_paise: int
    day_low_paise: int
    mrp_paise: int


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
