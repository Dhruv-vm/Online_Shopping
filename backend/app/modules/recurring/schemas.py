import datetime
import uuid

from pydantic import BaseModel, Field, model_validator


class RecurringScheduleIn(BaseModel):
    day_of_month: int = Field(..., ge=1, le=28)
    start_date: datetime.date
    end_date: datetime.date | None = None

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class RecurringBasketCreate(RecurringScheduleIn):
    name: str = Field(default="Basket Monthly Essentials", min_length=2, max_length=120)
    delivery_address_id: uuid.UUID | None = None


class RecurringBasketUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    day_of_month: int | None = Field(default=None, ge=1, le=28)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    clear_end_date: bool = False
    delivery_address_id: uuid.UUID | None = None
    # listing_id -> quantity (0 removes the item)
    quantities: dict[uuid.UUID, int] | None = None


class RecurringItem(BaseModel):
    listing_id: uuid.UUID
    quantity: int
    product_name: str
    variant_name: str | None = None
    retailer_name: str
    unit_price_paise_at_setup: int


class CheckLine(BaseModel):
    listing_id: uuid.UUID
    product_name: str
    retailer_name: str
    quantity: int
    status: str  # OK | PRICE_CHANGED | LOW_STOCK | OUT_OF_STOCK | UNAVAILABLE | NOT_DELIVERABLE
    previous_unit_price_paise: int
    current_unit_price_paise: int | None = None
    offer_unit_discount_paise: int = 0
    final_unit_price_paise: int | None = None
    available_quantity: int = 0
    offers: list[str] = Field(default_factory=list)
    line_total_paise: int = 0
    note: str | None = None


class PreOrderCheck(BaseModel):
    checked_at: datetime.datetime
    scheduled_for: datetime.date | None
    lines: list[CheckLine]
    orderable_lines: int
    items_total_paise: int  # current prices after live offers, orderable lines only
    previous_total_paise: int  # same lines at set-up prices
    changes: list[str]
    delivery_address_set: bool
    note: str = (
        "Delivery fee and GST are calculated at checkout. Nothing is ordered or "
        "charged until you check out yourself."
    )


class RecurringRun(BaseModel):
    scheduled_for: datetime.date
    status: str
    items_total_paise: int | None = None
    changes: int = 0
    created_at: datetime.datetime


class RecurringBasketOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    day_of_month: int
    start_date: datetime.date
    end_date: datetime.date | None
    next_run_date: datetime.date | None
    skip_dates: list[datetime.date]
    delivery_address_id: uuid.UUID | None
    items: list[RecurringItem]
    autopay: str = "NOT_ENABLED"
    recent_runs: list[RecurringRun] = Field(default_factory=list)
    created_at: datetime.datetime


class LoadToCartResult(BaseModel):
    loaded: int
    skipped: list[str]
    message: str
