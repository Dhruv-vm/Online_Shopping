from __future__ import annotations

import datetime
import re
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClaimReviewStatus(StrEnum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class ClaimScope(StrEnum):
    PRODUCT = "PRODUCT"
    LISTING = "LISTING"


class ItemCondition(StrEnum):
    NEW = "NEW"
    REFURBISHED = "REFURBISHED"
    OPEN_BOX = "OPEN_BOX"
    PRE_OWNED = "PRE_OWNED"


def validate_http_url(url: str | None) -> str | None:
    if url is None:
        return None
    url_stripped = url.strip()
    if not url_stripped:
        return None
    if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", url_stripped, re.IGNORECASE):
        raise ValueError("Evidence reference must be a valid HTTP or HTTPS URL")
    return url_stripped


# ================= Public Schemas =================


class PublicClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    claim_scope: str
    claim_type: str
    claim_key: str
    claim_value: str
    review_status: str
    is_public_evidence: bool = False
    evidence_url: str | None = None
    evidence_type: str | None = None
    created_at: datetime.datetime
    reviewed_at: datetime.datetime | None = None


class PublicListingPassportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    item_condition: str
    seller_warranty: str | None = None
    packaging_notes: str | None = None
    fulfillment_notes: str | None = None
    claims: list[PublicClaimResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ListingBrief(BaseModel):
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    retailer_name: str
    selling_price_paise: int
    is_in_stock: bool
    item_condition: str = "NEW"


class PublicProductPassportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    product_id: uuid.UUID
    product_name: str
    brand: str
    category_name: str
    manufacturer: str | None = None
    country_of_origin: str | None = None
    model_number: str | None = None
    gtin_ean_upc: str | None = None
    materials: list[Any] = Field(default_factory=list)
    technical_specs: dict[str, Any] = Field(default_factory=dict)
    package_contents: list[str] = Field(default_factory=list)
    usage_instructions: str | None = None
    safety_instructions: str | None = None
    warranty_info: str | None = None
    certifications: list[Any] = Field(default_factory=list)
    claims: list[PublicClaimResponse] = Field(default_factory=list)
    listing_passport: PublicListingPassportResponse | None = None
    available_listings: list[ListingBrief] = Field(default_factory=list)
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None


# ================= Retailer Schemas =================


class RetailerListingPassportUpsertRequest(BaseModel):
    item_condition: ItemCondition = ItemCondition.NEW
    seller_warranty: str | None = Field(default=None, max_length=2000)
    packaging_notes: str | None = Field(default=None, max_length=2000)
    fulfillment_notes: str | None = Field(default=None, max_length=2000)


class RetailerClaimCreateRequest(BaseModel):
    claim_scope: ClaimScope = ClaimScope.LISTING
    claim_type: str = Field(min_length=2, max_length=64)
    claim_key: str = Field(min_length=2, max_length=128)
    claim_value: str = Field(min_length=1, max_length=5000)
    evidence_url: str | None = Field(default=None, max_length=1024)
    evidence_type: str = Field(default="DOCUMENT", max_length=64)
    evidence_notes: str | None = Field(default=None, max_length=2000)
    is_public_evidence: bool = False

    @field_validator("evidence_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return validate_http_url(v)


class RetailerClaimUpdateRequest(BaseModel):
    claim_type: str | None = Field(default=None, min_length=2, max_length=64)
    claim_key: str | None = Field(default=None, min_length=2, max_length=128)
    claim_value: str | None = Field(default=None, min_length=1, max_length=5000)
    evidence_url: str | None = Field(default=None, max_length=1024)
    evidence_type: str | None = Field(default=None, max_length=64)
    evidence_notes: str | None = Field(default=None, max_length=2000)
    is_public_evidence: bool | None = None

    @field_validator("evidence_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        return validate_http_url(v)


class RetailerClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    passport_id: uuid.UUID | None = None
    listing_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    claim_scope: str
    claim_type: str
    claim_key: str
    claim_value: str
    evidence_url: str | None = None
    evidence_type: str
    evidence_notes: str | None = None
    is_public_evidence: bool
    review_status: str
    rejection_reason: str | None = None
    submitted_by_user_id: uuid.UUID | None = None
    reviewed_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RetailerListingPassportDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    listing_id: uuid.UUID
    retailer_id: uuid.UUID
    item_condition: str
    seller_warranty: str | None = None
    packaging_notes: str | None = None
    fulfillment_notes: str | None = None
    claims: list[RetailerClaimResponse] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ================= Admin Schemas =================


class AdminProductPassportUpsertRequest(BaseModel):
    manufacturer: str | None = Field(default=None, max_length=255)
    country_of_origin: str | None = Field(default=None, max_length=100)
    model_number: str | None = Field(default=None, max_length=100)
    gtin_ean_upc: str | None = Field(default=None, max_length=100)
    materials: list[Any] = Field(default_factory=list)
    technical_specs: dict[str, Any] = Field(default_factory=dict)
    package_contents: list[str] = Field(default_factory=list)
    usage_instructions: str | None = Field(default=None, max_length=5000)
    safety_instructions: str | None = Field(default=None, max_length=5000)
    warranty_info: str | None = Field(default=None, max_length=5000)
    certifications: list[Any] = Field(default_factory=list)


class AdminClaimRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=3, max_length=1000)


class AdminClaimResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    passport_id: uuid.UUID | None = None
    listing_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    retailer_name: str | None = None
    product_id: uuid.UUID | None = None
    product_name: str | None = None
    claim_scope: str
    claim_type: str
    claim_key: str
    claim_value: str
    evidence_url: str | None = None
    evidence_type: str
    evidence_notes: str | None = None
    is_public_evidence: bool
    review_status: str
    rejection_reason: str | None = None
    submitted_by_user_id: uuid.UUID | None = None
    reviewed_by_user_id: uuid.UUID | None = None
    reviewed_at: datetime.datetime | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AdminClaimQueueResponse(BaseModel):
    items: list[AdminClaimResponse]
    total: int
    page: int
    limit: int
    pages: int
