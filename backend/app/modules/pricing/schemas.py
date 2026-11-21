import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.pricing.models import QuoteStatus


class TaxBreakdownSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hsn_code: str
    gst_rate_basis_points: int
    gst_rate_percentage: float
    taxable_base_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    is_intra_state: bool


class RetailerPricingBreakdownSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    retailer_id: uuid.UUID
    retailer_name: str
    retailer_state: str
    subtotal_paise: int
    delivery_fee_paise: int
    free_delivery_threshold_paise: int = 49900
    qualifies_for_free_delivery: bool
    amount_needed_for_free_delivery_paise: int


class QuoteItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    variant_id: uuid.UUID
    retailer_id: uuid.UUID
    product_title: str
    variant_title: str
    sku: str | None
    hsn_code: str
    gst_rate_basis_points: int
    quantity: int
    unit_original_price_paise: int
    unit_selling_price_paise: int
    unit_discount_paise: int
    unit_discounted_price_paise: int
    total_selling_price_paise: int
    taxable_base_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    retailer_name: str
    retailer_state: str
    # Discounts priced into this line (Version 2.0; empty when none or when a
    # price award replaced them).
    applied_discount_ids: list[uuid.UUID] = Field(default_factory=list)
    created_at: datetime


class QuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID | None = None
    cart_id: uuid.UUID | None = None
    delivery_address_id: uuid.UUID | None = None
    delivery_state: str | None = None
    subtotal_paise: int
    discount_total_paise: int
    delivery_fee_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    total_tax_paise: int
    total_payable_paise: int
    currency: str = "INR"
    status: QuoteStatus
    is_consumed: bool
    consumed_at: datetime | None = None
    expires_at: datetime
    superseded_by_quote_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Version 2.0: the discount code that applied (None if none was supplied or
    # it did not apply to any line) and every discount priced into the quote.
    discount_code: str | None = None
    discount_code_applied: bool = False
    applied_discount_ids: list[uuid.UUID] = Field(default_factory=list)
    items: list[QuoteItemResponse]
    retailer_breakdowns: list[RetailerPricingBreakdownSchema] = Field(
        default_factory=list
    )


class QuoteCreateRequest(BaseModel):
    delivery_address_id: uuid.UUID | None = None
    delivery_state: str | None = None
    # Optional discount code (exact, case-insensitive), sent by the cart's coupon field.
    # Validation and pricing happen only here; the frontend never computes a discount.
    discount_code: str | None = Field(default=None, max_length=50)


class QuoteValidationIssue(BaseModel):
    code: str  # e.g. "EXPIRED", "PRICE_CHANGED", "OUT_OF_STOCK", "INACTIVE_LISTING", "ADDRESS_CHANGED"
    message: str
    listing_id: uuid.UUID | None = None
    previous_value: Any | None = None
    current_value: Any | None = None


class QuoteValidationResponse(BaseModel):
    valid: bool
    reason: str | None = None
    message: str
    can_refresh: bool = True
    issues: list[QuoteValidationIssue] = Field(default_factory=list)
    quote: QuoteResponse
