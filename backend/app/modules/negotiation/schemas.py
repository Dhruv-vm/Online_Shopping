import datetime
import uuid

from pydantic import BaseModel, Field, model_validator


class RuleUpsertRequest(BaseModel):
    listing_id: uuid.UUID | None = None
    min_floor_price_paise: int | None = Field(None, gt=0)
    max_auto_discount_percent: float = Field(..., ge=0, le=50)
    bundle_quantity_threshold: int | None = Field(None, ge=2, le=10)
    bundle_extra_discount_percent: float = Field(0, ge=0, le=20)
    is_active: bool = True

    @model_validator(mode="after")
    def _bundle(self):
        if self.bundle_extra_discount_percent and not self.bundle_quantity_threshold:
            raise ValueError(
                "bundle_extra_discount_percent requires bundle_quantity_threshold"
            )
        return self


class RuleItem(BaseModel):
    id: uuid.UUID
    listing_id: uuid.UUID | None
    min_floor_price_paise: int | None
    max_auto_discount_percent: float
    bundle_quantity_threshold: int | None
    bundle_extra_discount_percent: float
    is_active: bool
    created_at: datetime.datetime


class StartRequest(BaseModel):
    target_price_paise: int | None = Field(None, gt=0)
    max_budget_paise: int | None = Field(None, gt=0)
    language: str = Field("en", min_length=2, max_length=8)


class CounterOfferRequest(BaseModel):
    session_id: uuid.UUID
    proposed_price_paise: int = Field(..., gt=0)


class AcceptRequest(BaseModel):
    session_id: uuid.UUID


class NegotiationMessage(BaseModel):
    role: str
    text: str
    at: datetime.datetime


class NegotiationLine(BaseModel):
    listing_id: uuid.UUID
    product_name: str
    quantity: int
    list_unit_price_paise: int
    offer_unit_price_paise: int
    negotiable: bool


class NegotiationSessionResponse(BaseModel):
    id: uuid.UUID
    status: str
    language: str
    language_fallback: bool
    current_round: int
    max_rounds: int
    list_total_paise: int
    current_offer_paise: int
    savings_paise: int
    final_accepted_price_paise: int | None
    within_budget: bool | None
    lines: list[NegotiationLine]
    messages: list[NegotiationMessage]
    expires_at: datetime.datetime
    quote_id: uuid.UUID | None = None
    quote_total_payable_paise: int | None = None
    quote_expires_at: datetime.datetime | None = None
